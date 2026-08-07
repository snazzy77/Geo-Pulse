from __future__ import annotations

import warnings

import numpy as np
import pandas as pd

from geo_pulse.modeling.evaluator import regression_metrics
from geo_pulse.modeling.mixed_effects import FittedModel, fit_mixed_effects
from geo_pulse.modeling.predictor import add_predictions
from geo_pulse.schemas.models import Coefficient, ModelSummary


def train_model(
    data: pd.DataFrame,
    model_target: str,
    original_target: str,
    group_column: str,
    fixed_effects: list[str],
    target_transform: str = "log",
) -> tuple[FittedModel, pd.DataFrame, ModelSummary]:
    fitted = fit_mixed_effects(data, model_target, group_column, fixed_effects)
    fitted.target_transform = target_transform
    with warnings.catch_warnings(record=True) as captured:
        warnings.simplefilter("always")
        predictions = add_predictions(data, fitted, original_target)
        if not fitted.is_mixed:
            random_effects = {str(group): 0.0 for group in data[group_column].unique()}
            prefix = f"C({group_column})[T."
            for name, estimate in fitted.result.params.items():
                if name.startswith(prefix) and name.endswith("]"):
                    random_effects[name[len(prefix) : -1]] = float(estimate)
        elif fitted.fixed_only_prediction:
            random_effects = {str(group): 0.0 for group in data[group_column].unique()}
        else:
            try:
                random_effects = {
                    str(group): float(np.asarray(effect, dtype=float).ravel()[0])
                    for group, effect in fitted.result.random_effects.items()
                }
            except ValueError as exc:
                if "singular covariance" not in str(exc).lower():
                    raise
                fitted.fixed_only_prediction = True
                random_effects = {str(group): 0.0 for group in data[group_column].unique()}
                fitted.warnings.append(
                    "The random-effect covariance reached a zero boundary; predictions use fixed "
                    "effects and neighborhood random effects are reported as zero."
                )
    metrics = regression_metrics(
        predictions[model_target], predictions[f"predicted_{model_target}"]
    )
    if fitted.is_mixed:
        fixed_parameters = fitted.result.fe_params
        standard_errors = fitted.result.bse_fe
    else:
        fixed_names = [
            name
            for name in fitted.result.params.index
            if not name.startswith(f"C({group_column})[")
        ]
        fixed_parameters = fitted.result.params.loc[fixed_names]
        standard_errors = fitted.result.bse.loc[fixed_names]
    fixed_names = list(fixed_parameters.index)
    coefficients = [
        Coefficient(
            name=name,
            estimate=float(fixed_parameters[name]),
            standard_error=float(standard_errors[name]),
            p_value=float(fitted.result.pvalues[name]),
        )
        for name in fixed_names
    ]
    fitted.warnings.extend(str(item.message) for item in captured)
    fitted.warnings = list(dict.fromkeys(fitted.warnings))
    summary = ModelSummary(
        model_type=fitted.model_type,
        formula=fitted.formula,
        converged=fitted.converged,
        row_count=len(data),
        group_count=int(data[group_column].nunique()),
        metrics=metrics,
        coefficients=coefficients,
        random_effects=random_effects,
        extra={
            "aic": float(fitted.result.aic),
            "bic": float(fitted.result.bic),
            "fit_warnings": fitted.warnings,
            "target_transform": target_transform,
            "model_target": model_target,
        },
    )
    return fitted, predictions, summary
