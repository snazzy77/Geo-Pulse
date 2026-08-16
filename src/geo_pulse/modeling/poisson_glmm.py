from __future__ import annotations

import warnings
from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.stats import norm
from statsmodels.genmod.bayes_mixed_glm import PoissonBayesMixedGLM

from geo_pulse.core.exceptions import ModelingError
from geo_pulse.modeling.formula_builder import build_formula
from geo_pulse.schemas.models import Coefficient, ModelSummary


@dataclass
class FittedPoissonModel:
    model: PoissonBayesMixedGLM
    result: object
    formula: str
    target: str
    group_column: str
    fixed_effects: list[str]


def _poisson_deviance(observed: np.ndarray, predicted: np.ndarray) -> float:
    predicted = np.clip(predicted, np.finfo(float).eps, None)
    term = np.zeros_like(observed, dtype=float)
    positive = observed > 0
    term[positive] = observed[positive] * np.log(observed[positive] / predicted[positive])
    return float(2 * np.sum(term - (observed - predicted)))


def fit_poisson_glmm(
    data: pd.DataFrame,
    target: str,
    group_column: str,
    fixed_effects: list[str],
    alert_threshold: float = 2.0,
) -> tuple[FittedPoissonModel, pd.DataFrame, ModelSummary]:
    formula = build_formula(target, fixed_effects)
    variance_components = {"geographic_intercept": f"0 + C({group_column})"}
    fit_warnings: list[str] = []
    try:
        model = PoissonBayesMixedGLM.from_formula(formula, variance_components, data)
        with warnings.catch_warnings(record=True) as captured:
            warnings.simplefilter("always")
            result = model.fit_vb()
        fit_warnings.extend(str(item.message) for item in captured)
        if not bool(getattr(result, "optim_retvals", {}).get("success", True)):
            with warnings.catch_warnings(record=True) as captured:
                warnings.simplefilter("always")
                result = model.fit_map()
            fit_warnings.extend(str(item.message) for item in captured)
    except Exception as exc:  # noqa: BLE001 - statsmodels exposes optimizer errors variably
        raise ModelingError(f"Poisson mixed model failed: {exc}") from None

    fixed_linear = np.asarray(model.exog @ result.fe_mean, dtype=float)
    random_linear = np.asarray(model.exog_vc @ result.vc_mean, dtype=float).ravel()
    predicted = np.exp(np.clip(fixed_linear + random_linear, -20, 20))
    observed = data[target].to_numpy(dtype=float)
    predictions = data.copy()
    predictions[f"predicted_{target}"] = predicted
    predictions["residual"] = observed - predicted
    predictions["pearson_residual"] = predictions["residual"] / np.sqrt(
        np.clip(predicted, np.finfo(float).eps, None)
    )
    predictions["surveillance_alert"] = predictions["pearson_residual"] >= alert_threshold

    coefficients: list[Coefficient] = []
    for index, name in enumerate(model.exog_names):
        estimate = float(result.fe_mean[index])
        standard_error = float(result.fe_sd[index])
        p_value = float(2 * norm.sf(abs(estimate / standard_error)))
        coefficients.append(
            Coefficient(
                name=name,
                estimate=estimate,
                standard_error=standard_error,
                p_value=p_value,
            )
        )
    random_frame = result.random_effects()
    random_effects = {
        str(name): float(row["Mean"]) for name, row in random_frame.iterrows()
    }
    rmse = float(np.sqrt(np.mean(np.square(observed - predicted))))
    mae = float(np.mean(np.abs(observed - predicted)))
    null_prediction = np.repeat(observed.mean(), len(observed))
    null_deviance = _poisson_deviance(observed, null_prediction)
    deviance = _poisson_deviance(observed, predicted)
    pseudo_r_squared = 1.0 - deviance / null_deviance if null_deviance > 0 else 0.0
    converged = bool(getattr(result, "optim_retvals", {}).get("success", True))
    summary = ModelSummary(
        model_type="Bayesian Poisson GLMM with geographic random intercept",
        formula=formula + f" + (1 | {group_column})",
        converged=converged,
        row_count=len(data),
        group_count=int(data[group_column].nunique()),
        metrics={
            "rmse": rmse,
            "mae": mae,
            "poisson_deviance": deviance,
            "pseudo_r_squared": float(pseudo_r_squared),
        },
        coefficients=coefficients,
        random_effects=random_effects,
        extra={
            "family": "Poisson",
            "link": "log",
            "target": target,
            "alert_threshold_pearson_residual": float(alert_threshold),
            "alert_count": int(predictions["surveillance_alert"].sum()),
            "fit_warnings": list(dict.fromkeys(fit_warnings)),
        },
    )
    return FittedPoissonModel(model, result, formula, target, group_column, fixed_effects), predictions, summary
