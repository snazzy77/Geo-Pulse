from fastapi import APIRouter, Depends

from geo_pulse.api.dependencies import get_settings
from geo_pulse.core.config import Settings

router = APIRouter(prefix="/datasets", tags=["datasets"])


@router.get("")
def list_datasets(settings: Settings = Depends(get_settings)) -> dict[str, list[str]]:
    root = settings.resolve(settings.data_dir)
    supported = {".csv", ".parquet", ".pq", ".json", ".jsonl", ".geojson"}
    files = [
        str(path.relative_to(root)) for path in root.rglob("*") if path.suffix.lower() in supported
    ]
    return {"datasets": sorted(files)}
