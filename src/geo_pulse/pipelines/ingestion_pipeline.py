from pathlib import Path

import pandas as pd

from geo_pulse.ingestion.geocoder import require_coordinates
from geo_pulse.ingestion.property_loader import load_table
from geo_pulse.ingestion.validators import validate_amenities, validate_properties


def run_ingestion(
    property_path: str | Path,
    amenity_path: str | Path,
    target: str,
    group_column: str,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    properties = validate_properties(
        require_coordinates(load_table(property_path)), target, group_column
    )
    amenities = validate_amenities(load_table(amenity_path))
    return properties, amenities
