from pathlib import Path

import pandas as pd


class DatasetStore:
    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def write_csv(self, frame: pd.DataFrame, relative_path: str | Path) -> Path:
        target = self.root / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        frame.to_csv(target, index=False)
        return target

    def read_csv(self, relative_path: str | Path) -> pd.DataFrame:
        return pd.read_csv(self.root / relative_path)
