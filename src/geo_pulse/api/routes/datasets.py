from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from geo_pulse.api.dependencies import get_settings
from geo_pulse.core.config import Settings
from geo_pulse.ingestion.property_loader import load_table
from geo_pulse.ingestion.schema_mapper import inspect_dataframe_schema
from geo_pulse.schemas.datasets import SchemaInspection

router = APIRouter(prefix="/datasets", tags=["datasets"])


@router.get("")
def list_datasets(settings: Settings = Depends(get_settings)) -> dict[str, list[str]]:
    root = settings.resolve(settings.data_dir)
    supported = {".csv", ".parquet", ".pq", ".json", ".jsonl", ".geojson"}
    files = [
        str(path.relative_to(root)) for path in root.rglob("*") if path.suffix.lower() in supported
    ]
    return {"datasets": sorted(files)}


@router.post("/inspect", response_model=SchemaInspection)
async def inspect_dataset(
    data: UploadFile = File(...),
    settings: Settings = Depends(get_settings),
) -> SchemaInspection:
    suffix = Path(data.filename or "").suffix.lower()
    supported = {".csv", ".json", ".jsonl", ".parquet", ".pq", ".geojson", ".gpkg"}
    if suffix not in supported:
        raise HTTPException(
            status_code=422,
            detail="Inspection supports CSV, JSON, JSONL, Parquet, GeoJSON, and GeoPackage files",
        )
    target_dir = settings.resolve(settings.data_dir) / "uploads" / uuid4().hex
    target_dir.mkdir(parents=True, exist_ok=False)
    target = target_dir / f"inspection{suffix}"
    size = 0
    try:
        with target.open("wb") as stream:
            while chunk := await data.read(1024 * 1024):
                size += len(chunk)
                if size > 25 * 1024 * 1024:
                    raise HTTPException(status_code=413, detail="Dataset exceeds the 25 MB limit")
                stream.write(chunk)
        return inspect_dataframe_schema(load_table(target), settings.schema.get("aliases"))
    finally:
        await data.close()
