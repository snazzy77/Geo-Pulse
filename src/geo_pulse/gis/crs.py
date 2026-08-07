from __future__ import annotations

from typing import Any

import numpy as np
from pyproj import CRS, Transformer


def select_local_projected_crs(latitude: float, longitude: float) -> CRS:
    """Select a meter-based CRS centered on a WGS84 location."""
    if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
        raise ValueError("WGS84 latitude/longitude are outside valid bounds")
    if -80 <= latitude <= 84:
        zone = min(60, max(1, int((longitude + 180) // 6) + 1))
        return CRS.from_epsg((32600 if latitude >= 0 else 32700) + zone)
    return CRS.from_proj4(
        f"+proj=aeqd +lat_0={latitude} +lon_0={longitude} +datum=WGS84 +units=m +no_defs +type=crs"
    )


def project_coordinates(coordinates: np.ndarray, projected_crs: CRS | None = None) -> np.ndarray:
    """Project WGS84 ``[latitude, longitude]`` pairs into local metric X/Y coordinates."""
    coords = np.asarray(coordinates, dtype=float)
    if coords.ndim != 2 or coords.shape[1] != 2 or len(coords) == 0:
        raise ValueError("Coordinates must be a non-empty Nx2 latitude/longitude array")
    center = coords.mean(axis=0)
    destination = projected_crs or select_local_projected_crs(float(center[0]), float(center[1]))
    transformer = Transformer.from_crs(4326, destination, always_xy=True)
    x, y = transformer.transform(coords[:, 1], coords[:, 0])
    return np.column_stack([x, y])


def local_xy_m(coordinates: np.ndarray, origin: np.ndarray | None = None) -> np.ndarray:
    """Return accurate local metric coordinates using an automatically selected projection."""
    coords = np.asarray(coordinates, dtype=float)
    anchor = np.asarray(origin, dtype=float) if origin is not None else coords.mean(axis=0)
    projected_crs = select_local_projected_crs(float(anchor[0]), float(anchor[1]))
    return project_coordinates(coords, projected_crs)


def auto_project_gdf(gdf: Any) -> Any:
    """Project a GeoDataFrame to an automatically selected local meter-based CRS."""
    if getattr(gdf, "empty", True):
        raise ValueError("Cannot project an empty GeoDataFrame")
    source = gdf if getattr(gdf, "crs", None) is not None else gdf.set_crs(4326)
    wgs84 = source.to_crs(4326)
    center = wgs84.geometry.unary_union.centroid
    return source.to_crs(select_local_projected_crs(center.y, center.x))
