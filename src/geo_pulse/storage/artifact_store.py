import json
from pathlib import Path
from typing import Any


class ArtifactStore:
    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def path(self, category: str, run_id: str, suffix: str) -> Path:
        directory = self.root / category
        directory.mkdir(parents=True, exist_ok=True)
        return directory / f"{run_id}.{suffix.lstrip('.')}"

    def write_json(self, category: str, run_id: str, payload: Any) -> Path:
        target = self.path(category, run_id, "json")
        with target.open("w", encoding="utf-8") as stream:
            json.dump(payload, stream, indent=2, default=str)
        return target
