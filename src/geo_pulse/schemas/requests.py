from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from geo_pulse.schemas.datasets import AnalysisKind, DatasetColumnMapping, TargetTransform


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
    analysis_kind: AnalysisKind = "auto"

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
    analysis_kind: AnalysisKind = "auto"

    def to_analysis_request(self) -> AnalysisRequest:
        return AnalysisRequest(
            question=self.question,
            property_path=self.data_path,
            output_dir=self.output_dir,
            analysis_mode="generic",
            column_mapping=self.column_mapping,
            target_transform=self.target_transform,
            analysis_kind=self.analysis_kind,
        )


class HealthAnalysisRequest(BaseModel):
    question: str = Field(min_length=3, max_length=1000)
    outcome_path: Path
    hazard_path: Path
    column_mapping: DatasetColumnMapping | None = None
    buffer_m: float = Field(default=2000, ge=100, le=25_000)
    alert_threshold: float = Field(default=2.0, ge=1.0, le=5.0)
    demographic_controls: list[
        Literal["median_household_income", "percent_below_poverty", "percent_age_65_plus"]
    ] = Field(default_factory=list)
    include_current_air_quality: bool = False
    output_dir: Path | None = None


class PlacesSurveillanceRequest(BaseModel):
    question: str = Field(min_length=3, max_length=1000)
    place: str = Field(default="Seattle, Washington, USA", min_length=3, max_length=200)
    county_fips: str = Field(default="53033", pattern=r"^\d{5}$")
    measure_id: str = Field(default="CASTHMA", pattern=r"^[A-Z][A-Z0-9_]{1,39}$")
    buffer_m: float = Field(default=2000, ge=100, le=25_000)
    alert_threshold: float = Field(default=2.0, ge=1.0, le=5.0)
    demographic_controls: list[
        Literal["median_household_income", "percent_below_poverty", "percent_age_65_plus"]
    ] = Field(
        default_factory=lambda: [
            "median_household_income",
            "percent_below_poverty",
            "percent_age_65_plus",
        ]
    )
    hazard_types: list[Literal["industrial_zone", "factory", "refinery", "power_plant"]] = Field(
        default_factory=lambda: ["industrial_zone", "factory", "refinery", "power_plant"]
    )
    max_hazards_per_type: int = Field(default=1000, ge=1, le=5000)
    output_dir: Path | None = None
