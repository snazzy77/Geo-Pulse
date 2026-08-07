import numpy as np
import pandas as pd


def residual_vector(frame: pd.DataFrame, column: str = "residual") -> np.ndarray:
    values = pd.to_numeric(frame[column], errors="coerce").to_numpy(dtype=float)
    if not np.isfinite(values).all():
        raise ValueError("Residual vector contains non-finite values")
    return values
