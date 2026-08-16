from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
import statsmodels.api as sm
import statsmodels.formula.api as smf

from geo_pulse.core.exceptions import ModelingError
from geo_pulse.modeling.formula_builder import build_formula
from geo_pulse.schemas.models import Coefficient, ModelSummary


@dataclass
class FittedPoissonGLM:
    result: object
    formula: str
    target: str
    fixed_effects: list[str]
    offset_column: str


def _poisson_deviance(observed: np.ndarray, predicted: np.ndarray) -> float:
    predicted = np.clip(predicted, np.finfo(float).eps, None)
    term = np.zeros_like(observed, dtype=float)
    positive = observed > 0
    term[positive] = observed[positive] * np.log(observed[positive] / predicted[positive])
    return float(2 * np.sum(term - (observed - predicted)))


def fit_population_offset_poisson_glm(
    data: pd.DataFrame,
    target: str,
    fixed_effects: list[str],
    offset_column: str,
    alert_threshold: float = 2.0,
) -> tuple[FittedPoissonGLM, pd.DataFrame, ModelSummary]:
    """Fit a tract-level Poisson rate model using log population as an offset."""
    population = pd.to_numeric(data[offset_column], errors="coerce").to_numpy(dtype=float)
    if not np.isfinite(population).all() or np.any(population <= 0):
        raise ModelingError("Poisson population offset must contain positive finite values")
    offset = np.log(population)
    formula = build_formula(target, fixed_effects)
    try:
        model = smf.glm(
            formula=formula,
            data=data,
            family=sm.families.Poisson(link=sm.families.links.Log()),
            offset=offset,
        )
        result = model.fit()
    except Exception as exc:  # noqa: BLE001 - statsmodels surfaces several fit exceptions
        raise ModelingError(f"Population-offset Poisson model failed: {exc}") from None

    predicted = np.asarray(result.predict(data, offset=offset), dtype=float)
    observed = data[target].to_numpy(dtype=float)
    predictions = data.copy()
    predictions[f"predicted_{target}"] = predicted
    predictions["residual"] = observed - predicted
    predictions["pearson_residual"] = predictions["residual"] / np.sqrt(
        np.clip(predicted, np.finfo(float).eps, None)
    )
    predictions["surveillance_alert"] = predictions["pearson_residual"] >= alert_threshold
    coefficients = [
        Coefficient(
            name=str(name),
            estimate=float(result.params[name]),
            standard_error=float(result.bse[name]),
            p_value=float(result.pvalues[name]),
        )
        for name in result.params.index
    ]
    null_rate = observed.sum() / population.sum()
    null_prediction = population * null_rate
    deviance = _poisson_deviance(observed, predicted)
    null_deviance = _poisson_deviance(observed, null_prediction)
    pseudo_r_squared = 1 - deviance / null_deviance if null_deviance > 0 else 0.0
    summary = ModelSummary(
        model_type="Poisson GLM with log-population offset",
        formula=f"{formula} + offset(log({offset_column}))",
        converged=bool(getattr(result, "converged", True)),
        row_count=len(data),
        group_count=int(data["county_fips"].nunique()) if "county_fips" in data else 1,
        metrics={
            "rmse": float(np.sqrt(np.mean(np.square(observed - predicted)))),
            "mae": float(np.mean(np.abs(observed - predicted))),
            "poisson_deviance": deviance,
            "pseudo_r_squared": float(pseudo_r_squared),
        },
        coefficients=coefficients,
        extra={
            "family": "Poisson",
            "link": "log",
            "target": target,
            "offset_column": offset_column,
            "alert_threshold_pearson_residual": float(alert_threshold),
            "alert_count": int(predictions["surveillance_alert"].sum()),
        },
    )
    return (
        FittedPoissonGLM(result, formula, target, fixed_effects, offset_column),
        predictions,
        summary,
    )
