import numpy as np

from geo_pulse.core.constants import EARTH_RADIUS_M


def local_xy_m(coordinates: np.ndarray, origin: np.ndarray | None = None) -> np.ndarray:
    """Approximate WGS84 coordinates as local meters for neighborhood-scale work."""
    coords = np.asarray(coordinates, dtype=float)
    anchor = np.asarray(origin if origin is not None else coords.mean(axis=0), dtype=float)
    lat = np.radians(coords[:, 0])
    lon = np.radians(coords[:, 1])
    lat0, lon0 = np.radians(anchor)
    x = (lon - lon0) * np.cos(lat0) * EARTH_RADIUS_M
    y = (lat - lat0) * EARTH_RADIUS_M
    return np.column_stack([x, y])
