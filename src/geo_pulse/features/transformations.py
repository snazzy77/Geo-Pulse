import numpy as np
import pandas as pd


def add_log_target(frame: pd.DataFrame, target: str) -> tuple[pd.DataFrame, str]:
    result = frame.copy()
    column = f"log_{target}"
    result[column] = np.log(result[target].clip(lower=np.finfo(float).eps))
    return result, column


def fill_numeric_medians(frame: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    result = frame.copy()
    for column in columns:
        if column in result:
            values = pd.to_numeric(result[column], errors="coerce")
            result[column] = values.fillna(values.median())
    return result
