from pydantic import BaseModel, Field


class AnalysisResponse(BaseModel):
    run_id: str
    status: str
    summary: str
    findings: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    artifacts: dict[str, str] = Field(default_factory=dict)
