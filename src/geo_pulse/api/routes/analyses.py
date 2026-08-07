import json
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from starlette.concurrency import run_in_threadpool

from geo_pulse.agent.orchestrator import execute
from geo_pulse.api.dependencies import get_settings
from geo_pulse.core.config import Settings
from geo_pulse.pipelines.external_pipeline import run_external_analysis
from geo_pulse.sample_data import generate_sample_data
from geo_pulse.schemas.datasets import DatasetColumnMapping, TargetTransform
from geo_pulse.schemas.external import ExternalAnalysisRequest
from geo_pulse.schemas.reports import AnalysisResponse
from geo_pulse.schemas.requests import AnalysisRequest, SpatialAnalysisRequest
from geo_pulse.storage.run_repository import RunRepository

router = APIRouter(prefix="/analyses", tags=["analyses"])
ALLOWED_UPLOAD_SUFFIXES = {".csv", ".json", ".jsonl", ".parquet", ".pq", ".geojson", ".gpkg"}
MAX_UPLOAD_BYTES = 25 * 1024 * 1024


async def _save_upload(upload: UploadFile, directory: Path, label: str) -> Path:
    suffix = Path(upload.filename or "").suffix.lower()
    if suffix not in ALLOWED_UPLOAD_SUFFIXES:
        allowed = ", ".join(sorted(ALLOWED_UPLOAD_SUFFIXES))
        raise HTTPException(status_code=422, detail=f"{label} must use one of: {allowed}")
    target = directory / f"{label}{suffix}"
    size = 0
    try:
        with target.open("wb") as stream:
            while chunk := await upload.read(1024 * 1024):
                size += len(chunk)
                if size > MAX_UPLOAD_BYTES:
                    raise HTTPException(status_code=413, detail=f"{label} exceeds the 25 MB limit")
                stream.write(chunk)
    except Exception:
        target.unlink(missing_ok=True)
        raise
    finally:
        await upload.close()
    return target


@router.post("", response_model=AnalysisResponse)
def create_analysis(
    request: AnalysisRequest, settings: Settings = Depends(get_settings)
) -> AnalysisResponse:
    return execute(request, settings)


@router.post("/upload", response_model=AnalysisResponse)
async def create_uploaded_analysis(
    question: str = Form(..., min_length=3, max_length=1000),
    properties: UploadFile = File(...),
    amenities: UploadFile = File(...),
    target: str = Form("price"),
    group_column: str = Form("neighborhood"),
    settings: Settings = Depends(get_settings),
) -> AnalysisResponse:
    upload_dir = settings.resolve(settings.data_dir) / "uploads" / uuid4().hex
    upload_dir.mkdir(parents=True, exist_ok=False)
    property_path = await _save_upload(properties, upload_dir, "properties")
    amenity_path = await _save_upload(amenities, upload_dir, "amenities")
    request = AnalysisRequest(
        question=question,
        property_path=property_path,
        amenity_path=amenity_path,
        target=target,
        group_column=group_column,
    )
    return await run_in_threadpool(execute, request, settings)


@router.post("/spatial-upload", response_model=AnalysisResponse)
async def create_spatial_upload_analysis(
    question: str = Form(..., min_length=3, max_length=1000),
    data: UploadFile = File(...),
    column_mapping: str | None = Form(None),
    target_transform: TargetTransform = Form("auto"),
    settings: Settings = Depends(get_settings),
) -> AnalysisResponse:
    upload_dir = settings.resolve(settings.data_dir) / "uploads" / uuid4().hex
    upload_dir.mkdir(parents=True, exist_ok=False)
    data_path = await _save_upload(data, upload_dir, "spatial-data")
    try:
        mapping = (
            DatasetColumnMapping.model_validate(json.loads(column_mapping))
            if column_mapping
            else None
        )
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=422, detail=f"Invalid column_mapping JSON: {exc}") from None
    request = SpatialAnalysisRequest(
        question=question,
        data_path=data_path,
        column_mapping=mapping,
        target_transform=target_transform,
    ).to_analysis_request()
    return await run_in_threadpool(execute, request, settings)


@router.post("/demo", response_model=AnalysisResponse)
async def create_demo_analysis(
    question: str = "How does park distance affect home price?",
    settings: Settings = Depends(get_settings),
) -> AnalysisResponse:
    property_path, amenity_path = generate_sample_data(
        settings.resolve(settings.data_dir) / "samples", settings.random_seed
    )
    request = AnalysisRequest(
        question=question,
        property_path=property_path,
        amenity_path=amenity_path,
    )
    return await run_in_threadpool(execute, request, settings)


@router.post("/external", response_model=AnalysisResponse)
async def create_external_analysis(
    request: ExternalAnalysisRequest,
    settings: Settings = Depends(get_settings),
) -> AnalysisResponse:
    return await run_in_threadpool(run_external_analysis, request, settings)


@router.get("/{run_id}")
def get_analysis(run_id: str, settings: Settings = Depends(get_settings)) -> dict:
    try:
        return RunRepository(settings.artifacts / "run_metadata").get(run_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Analysis run not found") from exc
