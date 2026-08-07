import numpy as np

from geo_pulse.gis.distance_calculator import nearest_distance_m
from geo_pulse.gis.spatial_weights import knn_weights


def test_haversine_distance_is_zero_for_same_point():
    point = np.array([[30.2672, -97.7431]])
    assert nearest_distance_m(point, point)[0] == 0


def test_knn_weights_are_row_standardized():
    coordinates = np.array([[30.0, -97.0], [30.01, -97.0], [30.02, -97.0]])
    weights = knn_weights(coordinates, k=1)
    np.testing.assert_allclose(weights.sum(axis=1), 1)
    np.testing.assert_allclose(np.diag(weights), 0)
