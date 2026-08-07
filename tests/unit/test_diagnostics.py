import numpy as np

from geo_pulse.diagnostics.morans_i import morans_i
from geo_pulse.gis.spatial_weights import knn_weights


def test_morans_i_returns_valid_permutation_probability():
    rng = np.random.default_rng(7)
    coordinates = rng.normal(size=(30, 2))
    values = rng.normal(size=30)
    result = morans_i(values, knn_weights(coordinates, 4), permutations=49, seed=7)
    assert -1 <= result.statistic <= 1
    assert 0 < result.p_value <= 1
    assert result.permutations == 49
