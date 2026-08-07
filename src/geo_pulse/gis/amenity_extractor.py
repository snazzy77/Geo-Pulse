import pandas as pd

ALIASES = {
    "bus_station": "transit",
    "station": "transit",
    "subway_entrance": "transit",
    "playground": "park",
    "garden": "park",
}


def normalize_amenity_types(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    values = result["amenity_type"].astype(str).str.lower().str.strip()
    result["amenity_type"] = values.replace(ALIASES)
    return result


def select_amenity(frame: pd.DataFrame, amenity_type: str) -> pd.DataFrame:
    return frame[frame["amenity_type"] == amenity_type.lower()].copy()
