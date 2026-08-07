from __future__ import annotations

import pandas as pd

from geo_pulse.core.exceptions import DataValidationError

PROPERTY_REQUIRED = {
    "property_id",
    "latitude",
    "longitude",
    "square_feet",
    "beds",
    "baths",
}
AMENITY_REQUIRED = {"amenity_id", "amenity_type", "latitude", "longitude"}


def _require_columns(frame: pd.DataFrame, required: set[str], label: str) -> None:
    missing = sorted(required - set(frame.columns))
    if missing:
        raise DataValidationError(f"{label} data is missing columns: {', '.join(missing)}")


def validate_properties(
    frame: pd.DataFrame, target: str = "price", group: str = "neighborhood"
) -> pd.DataFrame:
    required = PROPERTY_REQUIRED | {target, group}
    _require_columns(frame, required, "Property")
    clean = frame.copy()
    numeric = {"latitude", "longitude", "square_feet", "beds", "baths", target}
    for column in numeric:
        clean[column] = pd.to_numeric(clean[column], errors="coerce")
    clean = clean.dropna(subset=list(required))
    clean = clean.drop_duplicates(subset=["property_id"], keep="last")
    clean = clean[
        clean["latitude"].between(-90, 90)
        & clean["longitude"].between(-180, 180)
        & (clean[target] > 0)
        & (clean["square_feet"] > 0)
    ].reset_index(drop=True)
    if clean.empty:
        raise DataValidationError("No valid property rows remain after validation")
    return clean


def validate_amenities(frame: pd.DataFrame) -> pd.DataFrame:
    _require_columns(frame, AMENITY_REQUIRED, "Amenity")
    clean = frame.copy()
    clean["latitude"] = pd.to_numeric(clean["latitude"], errors="coerce")
    clean["longitude"] = pd.to_numeric(clean["longitude"], errors="coerce")
    clean["amenity_type"] = clean["amenity_type"].astype(str).str.lower().str.strip()
    clean = clean.dropna(subset=list(AMENITY_REQUIRED)).drop_duplicates("amenity_id")
    clean = clean[
        clean["latitude"].between(-90, 90) & clean["longitude"].between(-180, 180)
    ].reset_index(drop=True)
    if clean.empty:
        raise DataValidationError("No valid amenity rows remain after validation")
    return clean
