import json
from pathlib import Path

from geo_pulse.core.exceptions import DataValidationError


def load_geojson(path: str | Path) -> dict:
    source = Path(path)
    if not source.exists():
        raise DataValidationError(f"Boundary file does not exist: {source}")
    with source.open("r", encoding="utf-8") as stream:
        document = json.load(stream)
    if document.get("type") not in {"Feature", "FeatureCollection"}:
        raise DataValidationError("Boundary file must be valid GeoJSON")
    return document
