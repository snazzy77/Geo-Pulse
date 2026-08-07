from pydantic import BaseModel, Field, field_validator


class ExternalAnalysisRequest(BaseModel):
    question: str = Field(min_length=3, max_length=1000)
    kaggle_dataset: str = "ericpierce/austinhousingprices"
    kaggle_filename: str = "austinHousingData.csv"
    column_mapping: dict[str, str] | None = None
    census_year: int = Field(default=2024, ge=2009, le=2100)
    max_rows: int = Field(default=500, ge=20, le=5000)

    @field_validator("kaggle_dataset")
    @classmethod
    def validate_kaggle_handle(cls, value: str) -> str:
        parts = value.strip().split("/")
        if len(parts) not in {2, 4} or any(not part for part in parts):
            raise ValueError("Kaggle dataset must use owner/dataset or owner/dataset/versions/N")
        if len(parts) == 4 and (parts[2] != "versions" or not parts[3].isdigit()):
            raise ValueError("Invalid versioned Kaggle dataset handle")
        return value.strip()

    @field_validator("kaggle_filename")
    @classmethod
    def validate_filename(cls, value: str) -> str:
        if (
            not value
            or value.startswith(("/", "\\"))
            or ".." in value.replace("\\", "/").split("/")
        ):
            raise ValueError("Kaggle filename must be a safe dataset-relative path")
        return value
