import numpy as np
import pandas as pd

from geo_pulse.core.exceptions import ModelingError


def add_log_target(frame: pd.DataFrame, target: str) -> tuple[pd.DataFrame, str]:
    result = frame.copy()
    column = f"log_{target}"
    result[column] = np.log(result[target].clip(lower=np.finfo(float).eps))
    return result, column


def add_model_target(
    frame: pd.DataFrame, target: str, transform: str = "log"
) -> tuple[pd.DataFrame, str, str]:
    values = pd.to_numeric(frame[target], errors="coerce")
    resolved = transform
    if transform == "auto":
        resolved = "log" if (values > 0).all() and abs(float(values.skew())) >= 1.0 else "none"
    if resolved == "log":
        if not (values > 0).all():
            raise ModelingError("Log target transformation requires strictly positive values")
        result, model_target = add_log_target(frame, target)
        return result, model_target, resolved
    if resolved == "none":
        result = frame.copy()
        result[target] = values
        return result, target, resolved
    raise ValueError(f"Unknown target transform: {transform}")


def fill_numeric_medians(frame: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    result = frame.copy()
    for column in columns:
        if column in result:
            values = pd.to_numeric(result[column], errors="coerce")
            result[column] = values.fillna(values.median())
    return result
