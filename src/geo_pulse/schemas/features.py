from pydantic import BaseModel


class FeatureDefinition(BaseModel):
    name: str
    description: str
    unit: str
    source: str


class FeatureSet(BaseModel):
    columns: list[str]
    catalog: list[FeatureDefinition]
    row_count: int
