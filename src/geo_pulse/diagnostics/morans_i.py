from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class MoranResult:
    statistic: float
    expected: float
    p_value: float
    permutations: int


def _statistic(values: np.ndarray, weights: np.ndarray) -> float:
    centered = values - values.mean()
    denominator = float(centered @ centered)
    weight_sum = float(weights.sum())
    if denominator == 0 or weight_sum == 0:
        return 0.0
    return float(len(values) / weight_sum * (centered @ weights @ centered) / denominator)


def morans_i(
    values: np.ndarray,
    weights: np.ndarray,
    permutations: int = 199,
    seed: int = 42,
) -> MoranResult:
    vector = np.asarray(values, dtype=float)
    observed = _statistic(vector, weights)
    expected = -1.0 / (len(vector) - 1) if len(vector) > 1 else 0.0
    rng = np.random.default_rng(seed)
    simulated = np.array(
        [_statistic(rng.permutation(vector), weights) for _ in range(permutations)]
    )
    extreme = np.count_nonzero(np.abs(simulated - expected) >= abs(observed - expected))
    p_value = float((extreme + 1) / (permutations + 1))
    return MoranResult(observed, expected, p_value, permutations)
