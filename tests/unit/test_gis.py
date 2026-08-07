import numpy as np

from geo_pulse.gis.crs import local_xy_m, select_local_projected_crs
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


def test_local_projection_is_selected_from_dataset_center():
    assert select_local_projected_crs(30.2672, -97.7431).to_epsg() == 32614
    assert select_local_projected_crs(51.5074, -0.1278).to_epsg() == 32630
    assert select_local_projected_crs(-33.8688, 151.2093).to_epsg() == 32756


def test_auto_projected_coordinates_are_metric():
    coordinates = np.array([[51.5074, -0.1278], [51.5164, -0.1278]])
    projected = local_xy_m(coordinates)
    distance = np.linalg.norm(projected[1] - projected[0])
    assert 990 < distance < 1010
