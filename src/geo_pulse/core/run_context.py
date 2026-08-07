from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from geo_pulse.core.constants import RUN_STATES


def _now() -> str:
    return datetime.now(UTC).isoformat()


@dataclass
class RunContext:
    question: str
    run_id: str = field(default_factory=lambda: uuid4().hex[:12])
    status: str = "received"
    created_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)
    stages: list[dict[str, Any]] = field(default_factory=list)
    artifacts: dict[str, str] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    error: str | None = None

    def transition(self, status: str, detail: str | None = None) -> None:
        if status not in RUN_STATES:
            raise ValueError(f"Unknown run status: {status}")
        self.status = status
        self.updated_at = _now()
        self.stages.append({"status": status, "at": self.updated_at, "detail": detail})

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
