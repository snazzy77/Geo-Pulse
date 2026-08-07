from pathlib import Path

import pandas as pd

from geo_pulse.core.exceptions import DataValidationError


def load_table(path: str | Path) -> pd.DataFrame:
    source = Path(path)
    if not source.exists():
        raise DataValidationError(f"Data source does not exist: {source}")
    suffix = source.suffix.lower()
    if suffix == ".csv":
        return pd.read_csv(source)
    if suffix in {".parquet", ".pq"}:
        return pd.read_parquet(source)
    if suffix in {".json", ".jsonl"}:
        return pd.read_json(source, lines=suffix == ".jsonl")
    if suffix in {".geojson", ".gpkg"}:
        try:
            import geopandas as gpd
        except ImportError as exc:
            raise DataValidationError("Geospatial files require geopandas") from exc
        return gpd.read_file(source)
    raise DataValidationError(f"Unsupported data format: {suffix}")


class LocalPropertyProvider:
    def load(self, source: Path) -> pd.DataFrame:
        return load_table(source)
