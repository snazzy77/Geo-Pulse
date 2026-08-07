import json

from fastapi import APIRouter, Depends, HTTPException

from geo_pulse.api.dependencies import get_settings
from geo_pulse.core.config import Settings

router = APIRouter(prefix="/models", tags=["models"])


@router.get("/{run_id}")
def get_model_summary(run_id: str, settings: Settings = Depends(get_settings)) -> dict:
    path = settings.artifacts / "models" / f"{run_id}-summary.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Model summary not found")
    return json.loads(path.read_text(encoding="utf-8"))
