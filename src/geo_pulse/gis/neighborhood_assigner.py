import pandas as pd

from geo_pulse.core.exceptions import DataValidationError


def require_group(frame: pd.DataFrame, column: str) -> pd.DataFrame:
    if column not in frame:
        raise DataValidationError(f"Missing geographic grouping column: {column}")
    result = frame.copy()
    result[column] = result[column].astype(str).str.strip()
    if (result[column] == "").any():
        raise DataValidationError(f"Geographic grouping column contains blank values: {column}")
    return result
