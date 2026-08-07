import importlib.util
import os
from pathlib import Path

from fastapi import APIRouter, Depends

from geo_pulse.api.dependencies import get_settings
from geo_pulse.core.config import Settings

router = APIRouter(prefix="/sources", tags=["sources"])


@router.get("/status")
def source_status(_: Settings = Depends(get_settings)) -> dict:
    return {
        "kagglehub_installed": importlib.util.find_spec("kagglehub") is not None,
        "osmnx_installed": importlib.util.find_spec("osmnx") is not None,
        "kaggle_authenticated": bool(os.getenv("KAGGLE_API_TOKEN"))
        or (Path.home() / ".kaggle" / "kaggle.json").exists(),
        "census_api_key_configured": bool(os.getenv("CENSUS_API_KEY")),
    }
