from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

from geo_pulse.schemas.datasets import AnalysisKind, DatasetColumnMapping, TargetTransform


class OSMFeatureDefinition(BaseModel):
    key: str
    label: str
    description: str


class OSMPlaceDatasetRequest(BaseModel):
    place: str = Field(min_length=2, max_length=200)
    feature_type: str
    max_rows: int = Field(default=1000, ge=1, le=5000)
    refresh: bool = False

    @field_validator("place", "feature_type")
    @classmethod
    def strip_text(cls, value: str) -> str:
        return value.strip()


class SpatialDatasetResponse(BaseModel):
    dataset_id: str
    provider: str
    place: str
    feature_type: str
    row_count: int
    total_features_found: int
    truncated: bool
    columns: list[str]
    preview: list[dict[str, object]] = Field(default_factory=list)
    local_path: str
    download_url: str
    attribution: str
    license_url: str
    cached: bool = False


class SpatialSourceAnalysisRequest(BaseModel):
    dataset_id: str = Field(pattern=r"^[0-9a-f]{12}$")
    question: str = Field(min_length=3, max_length=1000)
    column_mapping: DatasetColumnMapping | None = None
    target_transform: TargetTransform = "auto"
    analysis_kind: AnalysisKind = "auto"
