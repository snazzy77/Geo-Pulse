import numpy as np
from scipy.spatial import cKDTree

from geo_pulse.gis.crs import local_xy_m


def knn_weights(coordinates: np.ndarray, k: int = 5) -> np.ndarray:
    count = len(coordinates)
    if count < 2:
        raise ValueError("At least two coordinates are required")
    neighbors = min(max(1, k), count - 1)
    xy = local_xy_m(coordinates)
    _, indices = cKDTree(xy).query(xy, k=neighbors + 1)
    weights = np.zeros((count, count), dtype=float)
    for row, neighbor_indices in enumerate(np.atleast_2d(indices)):
        weights[row, neighbor_indices[1:]] = 1.0
    weights = np.maximum(weights, weights.T)
    row_sums = weights.sum(axis=1, keepdims=True)
    return np.divide(weights, row_sums, out=np.zeros_like(weights), where=row_sums != 0)
