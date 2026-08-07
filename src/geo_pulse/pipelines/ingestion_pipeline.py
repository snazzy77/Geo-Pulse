from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from geo_pulse.core.exceptions import DataValidationError
from geo_pulse.ingestion.geocoder import require_coordinates
from geo_pulse.ingestion.property_loader import load_table
from geo_pulse.ingestion.schema_mapper import inspect_dataframe_schema, standardize_dataset
from geo_pulse.ingestion.validators import (
    validate_amenities,
    validate_properties,
    validate_spatial_records,
)
from geo_pulse.schemas.datasets import DatasetColumnMapping, SchemaInspection


@dataclass(frozen=True)
class SpatialIngestionResult:
    frame: pd.DataFrame
    fixed_effects: list[str]
    inspection: SchemaInspection
    mapping: DatasetColumnMapping


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


def run_spatial_ingestion(
    data_path: str | Path,
    column_mapping: DatasetColumnMapping | None = None,
    schema_aliases: dict[str, list[str]] | None = None,
) -> SpatialIngestionResult:
    source = load_table(data_path)
    inspection = inspect_dataframe_schema(source, schema_aliases)
    mapping = column_mapping or inspection.suggested_mapping
    if mapping is None:
        details = " ".join(inspection.warnings) or "Provide an explicit schema mapping."
        raise DataValidationError(
            f"Geo-Pulse could not safely infer this dataset schema. {details}"
        )
    standardized, fixed_effects = standardize_dataset(source, mapping)
    clean = validate_spatial_records(standardized, fixed_effects)
    return SpatialIngestionResult(clean, fixed_effects, inspection, mapping)
