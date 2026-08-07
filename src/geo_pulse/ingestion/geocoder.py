import pandas as pd

from geo_pulse.core.exceptions import DataValidationError


def require_coordinates(frame: pd.DataFrame) -> pd.DataFrame:
    if not {"latitude", "longitude"}.issubset(frame.columns):
        raise DataValidationError(
            "Local execution requires latitude and longitude. Configure an external geocoder adapter "
            "before using address-only data."
        )
    return frame
