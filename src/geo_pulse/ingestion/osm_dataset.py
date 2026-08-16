from __future__ import annotations

from pathlib import Path

import httpx
import numpy as np
import pandas as pd
from shapely.geometry import Point

from geo_pulse.core.exceptions import DataValidationError
from geo_pulse.gis.crs import auto_project_gdf
from geo_pulse.schemas.sources import OSMFeatureDefinition

OSM_DATASET_CATALOG: dict[str, dict[str, object]] = {
    "industrial_zone": {
        "label": "Industrial zones",
        "description": "Land designated for industrial activity",
        "tags": {"landuse": "industrial"},
    },
    "factory": {
        "label": "Factories and works",
        "description": "Manufacturing works and factory facilities",
        "tags": {"man_made": "works"},
    },
    "refinery": {
        "label": "Refineries",
        "description": "Oil, gas, chemical, and refinery industrial sites",
        "tags": {"industrial": ["refinery", "oil", "gas", "chemical"]},
    },
    "power_plant": {
        "label": "Power plants",
        "description": "Electricity generation plants and generators",
        "tags": {"power": ["plant", "generator"]},
    },
    "school": {
        "label": "Schools",
        "description": "Schools, colleges, and universities",
        "tags": {"amenity": ["school", "college", "university"]},
    },
    "hospital": {
        "label": "Hospitals and clinics",
        "description": "Hospitals, clinics, and doctors' offices",
        "tags": {"amenity": ["hospital", "clinic", "doctors"]},
    },
    "park": {
        "label": "Parks and recreation",
        "description": "Parks, gardens, playgrounds, and recreation grounds",
        "tags": {
            "leisure": ["park", "garden", "playground"],
            "landuse": "recreation_ground",
        },
    },
    "transit": {
        "label": "Public transit",
        "description": "Public-transport platforms, bus stops, and rail stations",
        "tags": {
            "public_transport": True,
            "highway": "bus_stop",
            "railway": ["station", "halt", "tram_stop"],
        },
    },
    "pharmacy": {
        "label": "Pharmacies",
        "description": "Pharmacies and dispensing locations",
        "tags": {"amenity": "pharmacy"},
    },
    "library": {
        "label": "Libraries",
        "description": "Public and institutional libraries",
        "tags": {"amenity": "library"},
    },
    "cafe": {
        "label": "Cafés",
        "description": "Cafés and coffee shops",
        "tags": {"amenity": "cafe"},
    },
    "supermarket": {
        "label": "Supermarkets",
        "description": "Supermarkets and grocery stores",
        "tags": {"shop": ["supermarket", "grocery"]},
    },
    "charging_station": {
        "label": "EV charging stations",
        "description": "Electric-vehicle charging stations",
        "tags": {"amenity": "charging_station"},
    },
    "apartments": {
        "label": "Apartment buildings",
        "description": "Buildings tagged as apartments or residential",
        "tags": {"building": ["apartments", "residential"]},
    },
}


def osm_feature_catalog() -> list[OSMFeatureDefinition]:
    return [
        OSMFeatureDefinition(
            key=key,
            label=str(definition["label"]),
            description=str(definition["description"]),
        )
        for key, definition in OSM_DATASET_CATALOG.items()
    ]


def _overpass_url(endpoint: str) -> str:
    endpoint = endpoint.rstrip("/")
    return endpoint if endpoint.endswith("/interpreter") else f"{endpoint}/interpreter"


def _tag_filters(tags: dict[str, object]) -> list[str]:
    filters: list[str] = []
    for key, value in tags.items():
        values = value if isinstance(value, list) else [value]
        for item in values:
            filters.append(f'["{key}"]' if item is True else f'["{key}"="{item}"]')
    return filters


def _build_overpass_query(
    bbox: tuple[float, float, float, float], tags: dict[str, object], timeout_s: int
) -> str:
    west, south, east, north = bbox
    selectors = "".join(
        f"nwr{tag_filter}({south},{west},{north},{east});"
        for tag_filter in _tag_filters(tags)
    )
    return f"[out:json][timeout:{timeout_s}];({selectors});out center tags;"


def _request_overpass(
    endpoint: str, query: str, timeout_s: int, user_agent: str
) -> list[dict[str, object]]:
    response = httpx.post(
        _overpass_url(endpoint),
        data={"data": query},
        headers={"User-Agent": user_agent},
        timeout=timeout_s,
    )
    response.raise_for_status()
    payload = response.json()
    elements = payload.get("elements", [])
    if not isinstance(elements, list):
        raise TypeError("Overpass response did not contain an elements list")
    return elements


def fetch_osm_place_dataset(
    place: str,
    feature_type: str,
    max_rows: int = 1000,
    cache_dir: str | Path = ".cache/osmnx",
    request_timeout_s: int = 180,
    max_place_area_km2: float = 2500,
    user_agent: str = "Geo-Pulse/0.1 (local research application)",
    seed: int = 42,
    overpass_endpoints: list[str] | None = None,
    overpass_rate_limit: bool = False,
) -> tuple[pd.DataFrame, dict[str, object]]:
    """Download one controlled class of OSM features within a named place."""
    definition = OSM_DATASET_CATALOG.get(feature_type)
    if definition is None:
        choices = ", ".join(OSM_DATASET_CATALOG)
        raise DataValidationError(
            f"Unsupported OSM feature type {feature_type!r}. Choose one of: {choices}"
        )
    try:
        import osmnx as ox
    except ImportError as exc:
        raise DataValidationError("OpenStreetMap datasets require osmnx and geopandas") from exc
    ox.settings.use_cache = True
    ox.settings.cache_folder = str(Path(cache_dir))
    ox.settings.requests_timeout = request_timeout_s
    ox.settings.http_user_agent = user_agent
    ox.settings.overpass_rate_limit = overpass_rate_limit
    try:
        boundary = ox.geocode_to_gdf(place)
    except Exception as exc:  # noqa: BLE001 - provider surfaces varied network/geocoder errors
        raise DataValidationError(
            f"OpenStreetMap could not resolve place {place!r}: {exc}"
        ) from None
    if boundary.empty or boundary.geometry.is_empty.all():
        raise DataValidationError(f"OpenStreetMap returned no boundary for {place!r}")
    projected_boundary = auto_project_gdf(boundary)
    area_km2 = float(projected_boundary.geometry.area.sum() / 1_000_000)
    if not np.isfinite(area_km2) or area_km2 <= 0:
        raise DataValidationError(f"OpenStreetMap returned an invalid boundary for {place!r}")
    if area_km2 > max_place_area_km2:
        raise DataValidationError(
            f"{place!r} covers {area_km2:,.0f} km², above the configured "
            f"{max_place_area_km2:,.0f} km² safety limit. Choose a city, borough, or district."
        )
    wgs84_boundary = boundary.to_crs(4326)
    polygon = wgs84_boundary.geometry.union_all()
    bbox = tuple(float(value) for value in wgs84_boundary.total_bounds)
    query = _build_overpass_query(bbox, dict(definition["tags"]), request_timeout_s)
    endpoints = overpass_endpoints or [
        "https://overpass.private.coffee/api",
        "https://overpass-api.de/api",
    ]
    failures: list[str] = []
    elements: list[dict[str, object]] | None = None
    for endpoint in endpoints:
        try:
            candidate = _request_overpass(endpoint, query, request_timeout_s, user_agent)
            if candidate:
                elements = candidate
                break
            failures.append(f"{endpoint}: no matching records")
        except Exception as exc:  # noqa: BLE001 - Overpass backends raise varied exceptions
            failures.append(f"{endpoint}: {type(exc).__name__}")
    if elements is None:
        attempted = ", ".join(failures)
        raise DataValidationError(
            f"No {feature_type!r} records could be downloaded for {place!r}. "
            f"Attempts: {attempted}. Public services may be busy; try again later."
        )

    records: list[dict[str, object]] = []
    for element in elements:
        center = element.get("center", {})
        latitude = element.get("lat") if element.get("lat") is not None else center.get("lat")
        longitude = element.get("lon") if element.get("lon") is not None else center.get("lon")
        if latitude is None or longitude is None:
            continue
        latitude, longitude = float(latitude), float(longitude)
        if not polygon.covers(Point(longitude, latitude)):
            continue
        tags = element.get("tags", {})
        records.append(
            {
                "record_id": f"osm-{element.get('type', 'feature')}-{element.get('id')}",
                "feature_type": feature_type,
                "name": tags.get("name"),
                "latitude": latitude,
                "longitude": longitude,
                "geometry_type": "Point",
                "feature_area_m2": np.nan,
                "osm_element": str(element.get("type", "feature")),
                "osm_id": str(element.get("id", "")),
                "operator": tags.get("operator"),
                "source": "OpenStreetMap",
            }
        )
    if not records:
        raise DataValidationError(
            f"OpenStreetMap returned no {feature_type!r} features inside {place!r}"
        )
    frame = pd.DataFrame.from_records(records)
    frame = frame[
        frame["latitude"].between(-90, 90) & frame["longitude"].between(-180, 180)
    ].drop_duplicates("record_id")
    total = len(frame)
    if total == 0:
        raise DataValidationError("No valid coordinate records remain after OSM normalization")
    truncated = total > max_rows
    if truncated:
        frame = frame.sample(max_rows, random_state=seed).sort_values("record_id")
    frame = frame.reset_index(drop=True)
    metadata = {
        "provider": "OpenStreetMap",
        "place": place,
        "feature_type": feature_type,
        "query_tags": definition["tags"],
        "place_area_km2": area_km2,
        "total_features_found": total,
        "returned_rows": len(frame),
        "truncated": truncated,
        "attribution": "© OpenStreetMap contributors",
        "license_url": "https://www.openstreetmap.org/copyright",
    }
    return frame, metadata
