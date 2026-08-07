import numpy as np
import pandas as pd

from geo_pulse.modeling.mixed_effects import FittedModel


def add_predictions(data: pd.DataFrame, fitted: FittedModel, original_target: str) -> pd.DataFrame:
    result = data.copy()
    try:
        fitted_values = np.asarray(fitted.result.fittedvalues, dtype=float)
    except ValueError as exc:
        if "singular covariance" not in str(exc).lower():
            raise
        fitted_values = np.asarray(fitted.result.predict(data), dtype=float)
        fitted.fixed_only_prediction = True
        fitted.warnings.append(
            "The random-effect covariance reached a zero boundary; predictions use fixed effects "
            "and neighborhood random effects are reported as zero."
        )
    model_prediction = f"predicted_{fitted.target}"
    result[model_prediction] = fitted_values
    result["residual"] = result[fitted.target].to_numpy(dtype=float) - fitted_values
    result[f"predicted_{original_target}"] = (
        np.exp(fitted_values) if fitted.target_transform == "log" else fitted_values
    )
    return result
