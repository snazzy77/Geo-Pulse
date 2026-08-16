from geo_pulse.core.config import Settings
from geo_pulse.pipelines.source_acquisition_pipeline import acquire_osm_place_dataset
from geo_pulse.schemas.sources import OSMPlaceDatasetRequest, SpatialDatasetResponse


def fetch_openstreetmap_dataset_tool(
    request: OSMPlaceDatasetRequest, settings: Settings
) -> SpatialDatasetResponse:
    """Agent-facing no-key tool for acquiring a spatial dataset by place and feature type."""
    return acquire_osm_place_dataset(request, settings)
