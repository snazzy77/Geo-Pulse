from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

from geo_pulse.core.exceptions import DataValidationError
from geo_pulse.gis.crs import select_local_projected_crs
from geo_pulse.ingestion.schema_mapper import standardize_spatial_locations


def calculate_industrial_exposure(
    outcomes: pd.DataFrame,
    hazards: pd.DataFrame,
    buffer_m: float = 2000,
    aliases: dict[str, list[str]] | None = None,
) -> pd.DataFrame:
    """Count industrial hazard buffers intersecting each health geography or point."""
    try:
        import geopandas as gpd
    except ImportError as exc:
        raise DataValidationError("Industrial exposure scoring requires geopandas") from exc

    normalized_outcomes, _ = standardize_spatial_locations(outcomes, aliases)
    normalized_hazards, _ = standardize_spatial_locations(hazards, aliases)
    center_lat = float(normalized_outcomes["latitude"].mean())
    center_lon = float(normalized_outcomes["longitude"].mean())
    metric_crs = select_local_projected_crs(center_lat, center_lon)

    outcome_geometry = None
    if isinstance(outcomes, gpd.GeoDataFrame) and outcomes.geometry.name in outcomes:
        candidate = outcomes.loc[normalized_outcomes.index].copy()
        if candidate.crs is not None and candidate.geometry.notna().all():
            outcome_geometry = candidate.to_crs(metric_crs).geometry.reset_index(drop=True)
    if outcome_geometry is None:
        outcome_geometry = gpd.GeoSeries(
            gpd.points_from_xy(
                normalized_outcomes["longitude"], normalized_outcomes["latitude"]
            ),
            crs=4326,
        ).to_crs(metric_crs)

    outcome_gdf = gpd.GeoDataFrame(
        {"outcome_index": np.arange(len(normalized_outcomes))},
        geometry=outcome_geometry,
        crs=metric_crs,
    )
    hazard_points = gpd.GeoSeries(
        gpd.points_from_xy(
            normalized_hazards["longitude"], normalized_hazards["latitude"], crs=4326
        ),
        crs=4326,
    ).to_crs(metric_crs)
    hazard_buffers = gpd.GeoDataFrame(
        {"hazard_index": np.arange(len(hazard_points))},
        geometry=hazard_points.buffer(buffer_m),
        crs=metric_crs,
    )
    joined = gpd.sjoin(outcome_gdf, hazard_buffers, how="left", predicate="intersects")
    exposure = joined.groupby("outcome_index")["hazard_index"].count()

    representative = outcome_gdf.geometry.representative_point()
    outcome_xy = np.column_stack([representative.x, representative.y])
    hazard_xy = np.column_stack([hazard_points.x, hazard_points.y])
    nearest, _ = cKDTree(hazard_xy).query(outcome_xy, k=1)

    result = normalized_outcomes.copy()
    result["industrial_exposure_score"] = (
        result.index.to_series().map(exposure).fillna(0).astype(int)
    )
    result["nearest_industrial_site_km"] = nearest.astype(float) / 1000
    result.attrs["exposure_buffer_m"] = float(buffer_m)
    result.attrs["hazard_count"] = len(normalized_hazards)
    result.attrs["analysis_crs"] = metric_crs.to_string()
    return result
