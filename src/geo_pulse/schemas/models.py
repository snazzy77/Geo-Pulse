from typing import Any

from pydantic import BaseModel, Field


class Coefficient(BaseModel):
    name: str
    estimate: float
    standard_error: float | None = None
    p_value: float | None = None


class ModelSummary(BaseModel):
    model_type: str
    formula: str
    converged: bool
    row_count: int
    group_count: int
    metrics: dict[str, float]
    coefficients: list[Coefficient]
    random_effects: dict[str, float] = Field(default_factory=dict)
    extra: dict[str, Any] = Field(default_factory=dict)


class DiagnosticSummary(BaseModel):
    morans_i: float
    expected_i: float
    p_value: float
    permutations: int
    passed: bool
    decision: str
