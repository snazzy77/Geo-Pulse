from dataclasses import dataclass, field
from typing import Any


@dataclass
class AgentState:
    plan: dict[str, Any]
    observations: list[dict[str, Any]] = field(default_factory=list)
    completed: bool = False
