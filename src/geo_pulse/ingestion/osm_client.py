from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from geo_pulse.core.exceptions import DataValidationError


def fetch_amenities_for_place(place: str, tags: dict[str, object]) -> pd.DataFrame:
    """Fetch OSM features when the optional ``osm`` dependency is installed."""
    try:
        import osmnx as ox
    except ImportError as exc:
        raise DataValidationError(
            "Live OpenStreetMap retrieval requires installation with the 'osm' extra"
        ) from exc
    features = ox.features_from_place(place, tags)
    points = features.geometry.representative_point()
    result = pd.DataFrame(
        {
            "amenity_id": features.index.map(str),
            "amenity_type": "other",
            "latitude": points.y,
            "longitude": points.x,
        }
    )
    for key in ("amenity", "leisure", "public_transport", "highway"):
        if key in features:
            result.loc[features[key].notna(), "amenity_type"] = features.loc[
                features[key].notna(), key
            ].astype(str)
    return result.reset_index(drop=True)


OSM_AMENITY_TAGS: dict[str, dict[str, object]] = {
    "park": {
        "leisure": ["park", "garden", "playground"],
        "landuse": "recreation_ground",
    },
    "school": {"amenity": ["school", "college", "university"]},
    "transit": {
        "public_transport": True,
        "highway": "bus_stop",
        "railway": ["station", "halt", "tram_stop"],
    },
}


def _property_bbox(properties: pd.DataFrame, buffer_m: float) -> tuple[float, float, float, float]:
    mean_latitude = float(properties["latitude"].mean())
    latitude_buffer = buffer_m / 111_320
    longitude_buffer = buffer_m / (111_320 * max(np.cos(np.radians(mean_latitude)), 0.1))
    return (
        float(properties["longitude"].min() - longitude_buffer),
        float(properties["latitude"].min() - latitude_buffer),
        float(properties["longitude"].max() + longitude_buffer),
        float(properties["latitude"].max() + latitude_buffer),
    )


def _bbox_area_km2(bbox: tuple[float, float, float, float]) -> float:
    left, bottom, right, top = bbox
    height = (top - bottom) * 111.32
    width = (right - left) * 111.32 * np.cos(np.radians((top + bottom) / 2))
    return float(abs(height * width))


def fetch_amenities_for_properties(
    properties: pd.DataFrame,
    amenity_types: list[str],
    buffer_m: float = 1500,
    cache_dir: str | Path = ".cache/osmnx",
    request_timeout_s: int = 180,
    max_bbox_area_km2: float = 5000,
) -> pd.DataFrame:
    try:
        import osmnx as ox
    except ImportError as exc:
        raise DataValidationError("OSM enrichment requires the osmnx package") from exc
    bbox = _property_bbox(properties, buffer_m)
    area = _bbox_area_km2(bbox)
    if area > max_bbox_area_km2:
        raise DataValidationError(
            f"Property extent is {area:,.0f} km², above the OSM safety limit of "
            f"{max_bbox_area_km2:,.0f} km². Filter the Kaggle dataset to one market."
        )
    ox.settings.use_cache = True
    ox.settings.cache_folder = str(Path(cache_dir))
    ox.settings.requests_timeout = request_timeout_s
    configured_tags: dict[str, dict[str, object]] = {}
    combined_tags: dict[str, object] = {}
    for amenity_type in amenity_types:
        tags = OSM_AMENITY_TAGS.get(amenity_type)
        if tags is None:
            raise DataValidationError(f"No OSM tag mapping is configured for {amenity_type!r}")
        configured_tags[amenity_type] = tags
        for key, value in tags.items():
            existing = combined_tags.get(key)
            if existing is None or existing == value:
                combined_tags[key] = value
            elif existing is True or value is True:
                combined_tags[key] = True
            else:
                existing_values = existing if isinstance(existing, list) else [existing]
                new_values = value if isinstance(value, list) else [value]
                combined_tags[key] = list(dict.fromkeys([*existing_values, *new_values]))
    try:
        features = ox.features_from_bbox(bbox, combined_tags)
    except Exception as exc:
        raise DataValidationError(f"OSM Overpass request failed: {exc}") from exc
    rows: list[pd.DataFrame] = []
    for amenity_type, tags in configured_tags.items():
        if features.empty:
            continue
        matches = pd.Series(False, index=features.index)
        for key, expected in tags.items():
            if key not in features:
                continue
            values = features[key]
            if expected is True:
                matches |= values.notna()
            elif isinstance(expected, list):
                matches |= values.isin(expected)
            else:
                matches |= values == expected
        selected = features[matches]
        if selected.empty:
            continue
        points = selected.geometry.representative_point()
        identifiers = [
            "-".join(map(str, index)) if isinstance(index, tuple) else str(index)
            for index in selected.index
        ]
        rows.append(
            pd.DataFrame(
                {
                    "amenity_id": [
                        f"osm-{amenity_type}-{identifier}" for identifier in identifiers
                    ],
                    "amenity_type": amenity_type,
                    "latitude": points.y.to_numpy(),
                    "longitude": points.x.to_numpy(),
                }
            )
        )
    if not rows:
        raise DataValidationError(
            "OpenStreetMap returned no configured amenities for the property extent"
        )
    return pd.concat(rows, ignore_index=True).drop_duplicates("amenity_id")
