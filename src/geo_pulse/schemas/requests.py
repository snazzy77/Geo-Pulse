from pathlib import Path

from pydantic import BaseModel, Field, field_validator


class AnalysisRequest(BaseModel):
    question: str = Field(min_length=3, max_length=1000)
    property_path: Path
    amenity_path: Path | None = None
    target: str = "price"
    group_column: str = "neighborhood"
    output_dir: Path | None = None
    fixed_effects: list[str] | None = None

    @field_validator("target", "group_column")
    @classmethod
    def valid_column_name(cls, value: str) -> str:
        if not value.replace("_", "").isalnum():
            raise ValueError("Column names may contain only letters, numbers, and underscores")
        return value
