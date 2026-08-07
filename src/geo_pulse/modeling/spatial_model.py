import pandas as pd


def add_spatial_controls(frame: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    """Add bounded trend-surface controls used by the default correction policy."""
    result = frame.copy()
    result["latitude_centered"] = result["latitude"] - result["latitude"].mean()
    result["longitude_centered"] = result["longitude"] - result["longitude"].mean()
    return result, ["latitude_centered", "longitude_centered"]
