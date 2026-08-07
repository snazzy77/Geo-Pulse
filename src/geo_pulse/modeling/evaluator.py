import numpy as np
import pandas as pd


def regression_metrics(actual: pd.Series, predicted: pd.Series) -> dict[str, float]:
    y = actual.to_numpy(dtype=float)
    p = predicted.to_numpy(dtype=float)
    residual = y - p
    ss_res = float(np.sum(residual**2))
    ss_total = float(np.sum((y - y.mean()) ** 2))
    return {
        "rmse": float(np.sqrt(np.mean(residual**2))),
        "mae": float(np.mean(np.abs(residual))),
        "r_squared": float(1 - ss_res / ss_total) if ss_total > 0 else 0.0,
    }
