from __future__ import annotations

import numpy as np
import pandas as pd


def coordinate_array(frame: pd.DataFrame) -> np.ndarray:
    return frame[["latitude", "longitude"]].to_numpy(dtype=float)
