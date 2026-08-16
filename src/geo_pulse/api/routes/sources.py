import importlib.util
import os
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from starlette.concurrency import run_in_threadpool

from geo_pulse.api.dependencies import get_settings
from geo_pulse.core.config import Settings
from geo_pulse.core.exceptions import DataValidationError
from geo_pulse.ingestion.osm_dataset import osm_feature_catalog
from geo_pulse.pipelines.source_acquisition_pipeline import (
    acquire_osm_place_dataset,
    resolve_osm_dataset_path,
)
from geo_pulse.schemas.sources import OSMPlaceDatasetRequest, SpatialDatasetResponse

router = APIRouter(prefix="/sources", tags=["sources"])


@router.get("/status")
def source_status(_: Settings = Depends(get_settings)) -> dict:
    return {
        "kagglehub_installed": importlib.util.find_spec("kagglehub") is not None,
        "osmnx_installed": importlib.util.find_spec("osmnx") is not None,
        "kaggle_authenticated": bool(os.getenv("KAGGLE_API_TOKEN"))
        or (Path.home() / ".kaggle" / "kaggle.json").exists(),
        "census_api_key_configured": bool(os.getenv("CENSUS_API_KEY")),
        "cdc_places_available": True,
        "cdc_places_app_token_configured": bool(os.getenv("CDC_SOCRATA_APP_TOKEN")),
        "osm_api_key_required": False,
    }


@router.get("/catalog")
def source_catalog() -> dict:
    return {
        "providers": [
            {
                "key": "openstreetmap",
                "label": "OpenStreetMap",
                "authentication": "No API key",
                "capabilities": ["place search", "points of interest", "building footprints"],
                "feature_types": [feature.model_dump() for feature in osm_feature_catalog()],
                "attribution": "© OpenStreetMap contributors",
                "license_url": "https://www.openstreetmap.org/copyright",
            }
        ]
    }


@router.post("/osm/datasets", response_model=SpatialDatasetResponse)
async def create_osm_dataset(
    request: OSMPlaceDatasetRequest,
    settings: Settings = Depends(get_settings),
) -> SpatialDatasetResponse:
    try:
        return await run_in_threadpool(acquire_osm_place_dataset, request, settings)
    except DataValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/osm/datasets/{dataset_id}/download", response_class=FileResponse)
def download_osm_dataset(
    dataset_id: str,
    settings: Settings = Depends(get_settings),
) -> FileResponse:
    try:
        path = resolve_osm_dataset_path(dataset_id, settings)
    except DataValidationError:
        raise HTTPException(status_code=404, detail="Dataset not found") from None
    return FileResponse(path, filename=f"geo-pulse-osm-{dataset_id}.csv", media_type="text/csv")
