import numpy as np

from geo_pulse.core.constants import EARTH_RADIUS_M


def pairwise_haversine_m(origins: np.ndarray, destinations: np.ndarray) -> np.ndarray:
    origins_rad = np.radians(np.asarray(origins, dtype=float))
    destinations_rad = np.radians(np.asarray(destinations, dtype=float))
    lat1 = origins_rad[:, 0][:, None]
    lon1 = origins_rad[:, 1][:, None]
    lat2 = destinations_rad[:, 0][None, :]
    lon2 = destinations_rad[:, 1][None, :]
    delta_lat = lat2 - lat1
    delta_lon = lon2 - lon1
    a = np.sin(delta_lat / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin(delta_lon / 2) ** 2
    return 2 * EARTH_RADIUS_M * np.arcsin(np.sqrt(np.clip(a, 0, 1)))


def nearest_distance_m(origins: np.ndarray, destinations: np.ndarray) -> np.ndarray:
    if len(destinations) == 0:
        return np.full(len(origins), np.nan)
    return pairwise_haversine_m(origins, destinations).min(axis=1)
