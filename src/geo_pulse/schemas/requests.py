from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from geo_pulse.schemas.datasets import DatasetColumnMapping, TargetTransform


class AnalysisRequest(BaseModel):
    question: str = Field(min_length=3, max_length=1000)
    property_path: Path
    amenity_path: Path | None = None
    target: str = "price"
    group_column: str = "neighborhood"
    output_dir: Path | None = None
    fixed_effects: list[str] | None = None
    analysis_mode: Literal["housing", "generic"] = "housing"
    column_mapping: DatasetColumnMapping | None = None
    target_transform: TargetTransform = "log"

    @field_validator("target", "group_column")
    @classmethod
    def valid_column_name(cls, value: str) -> str:
        if not value.replace("_", "").isalnum():
            raise ValueError("Column names may contain only letters, numbers, and underscores")
        return value


class SpatialAnalysisRequest(BaseModel):
    question: str = Field(min_length=3, max_length=1000)
    data_path: Path
    column_mapping: DatasetColumnMapping | None = None
    output_dir: Path | None = None
    target_transform: TargetTransform = "auto"

    def to_analysis_request(self) -> AnalysisRequest:
        return AnalysisRequest(
            question=self.question,
            property_path=self.data_path,
            output_dir=self.output_dir,
            analysis_mode="generic",
            column_mapping=self.column_mapping,
            target_transform=self.target_transform,
        )
