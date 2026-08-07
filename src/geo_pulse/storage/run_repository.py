import json
from pathlib import Path

from geo_pulse.core.run_context import RunContext


class RunRepository:
    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def save(self, context: RunContext) -> Path:
        target = self.root / f"{context.run_id}.json"
        with target.open("w", encoding="utf-8") as stream:
            json.dump(context.to_dict(), stream, indent=2)
        return target

    def get(self, run_id: str) -> dict:
        with (self.root / f"{run_id}.json").open("r", encoding="utf-8") as stream:
            return json.load(stream)
