import numpy as np

from geo_pulse.gis.distance_calculator import pairwise_haversine_m


def count_within_radius(
    origins: np.ndarray, destinations: np.ndarray, radius_m: float
) -> np.ndarray:
    if len(destinations) == 0:
        return np.zeros(len(origins), dtype=int)
    return (pairwise_haversine_m(origins, destinations) <= radius_m).sum(axis=1)
