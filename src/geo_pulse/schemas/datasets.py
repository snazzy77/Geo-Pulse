from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator


class DatasetColumnMapping(BaseModel):
    """Maps an arbitrary spatial table onto Geo-Pulse's canonical analysis schema."""

    target_variable: str
    group_col: str
    fixed_features: list[str] = Field(min_length=1, max_length=50)
    lat_col: str | None = None
    lon_col: str | None = None
    geometry_col: str | None = None
    id_col: str | None = None
    source_crs: str = "EPSG:4326"

    @model_validator(mode="after")
    def require_spatial_source(self) -> DatasetColumnMapping:
        coordinate_pair = self.lat_col is not None and self.lon_col is not None
        if not coordinate_pair and self.geometry_col is None:
            raise ValueError("Provide both lat_col/lon_col or a geometry_col")
        if coordinate_pair and self.geometry_col is not None:
            raise ValueError("Choose lat_col/lon_col or geometry_col, not both")
        if (self.lat_col is None) != (self.lon_col is None):
            raise ValueError("lat_col and lon_col must be provided together")
        selected = [
            self.target_variable,
            self.group_col,
            *self.fixed_features,
            *([self.lat_col, self.lon_col] if coordinate_pair else []),
            *([self.geometry_col] if self.geometry_col else []),
            *([self.id_col] if self.id_col else []),
        ]
        if len(selected) != len(set(selected)):
            raise ValueError("Each mapped source column must have one role")
        return self


class SchemaInspection(BaseModel):
    columns: list[str]
    row_count: int
    sample_rows: list[dict[str, object]] = Field(default_factory=list)
    suggested_mapping: DatasetColumnMapping | None = None
    confidence: dict[str, float] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)


TargetTransform = Literal["auto", "log", "none"]
AnalysisKind = Literal["auto", "explore", "model"]
