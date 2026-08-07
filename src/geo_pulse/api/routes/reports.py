from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from geo_pulse.api.dependencies import get_settings
from geo_pulse.core.config import Settings

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/{run_id}/{artifact_type}", response_class=FileResponse)
def get_report_artifact(
    run_id: str, artifact_type: str, settings: Settings = Depends(get_settings)
) -> FileResponse:
    locations = {
        "report": settings.artifacts / "reports" / f"{run_id}.html",
        "map": settings.artifacts / "maps" / f"{run_id}.html",
    }
    path = locations.get(artifact_type)
    if path is None or not path.exists():
        raise HTTPException(status_code=404, detail="Artifact not found")
    return FileResponse(path)
