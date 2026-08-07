from pathlib import Path
from typing import Protocol

import pandas as pd


class PropertyProvider(Protocol):
    def load(self, source: Path) -> pd.DataFrame: ...
