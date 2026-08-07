from __future__ import annotations

import json
import re
from collections.abc import Iterable

import numpy as np
import pandas as pd
from pyproj import CRS, Transformer
from pyproj.exceptions import CRSError, ProjError
from shapely import wkt
from shapely.errors import GEOSException
from shapely.geometry import shape
from shapely.geometry.base import BaseGeometry

from geo_pulse.core.exceptions import DataValidationError
from geo_pulse.schemas.datasets import DatasetColumnMapping, SchemaInspection

ROLE_CANDIDATES: dict[str, tuple[str, ...]] = {
    "target": (
        "target",
        "price",
        "sale_price",
        "saleprice",
        "sold_price",
        "list_price",
        "listprice",
        "value",
        "rate",
        "count",
        "cases",
        "case_count",
        "disease_rate",
        "incidence_rate",
    ),
    "latitude": ("latitude", "lat", "y_coord", "y_coordinate", "ycoord"),
    "longitude": (
        "longitude",
        "lon",
        "lng",
        "long",
        "x_coord",
        "x_coordinate",
        "xcoord",
    ),
    "group": (
        "group_id",
        "group",
        "neighborhood",
        "neighbourhood",
        "zipcode",
        "zip_code",
        "postal_code",
        "zcta",
        "community_area",
        "district",
        "ward",
        "tract",
        "county",
        "region",
        "borough",
    ),
    "id": ("record_id", "property_id", "listing_id", "parcel_id", "case_number", "id"),
    "geometry": ("geometry", "geom", "wkt", "the_geom"),
}
ID_LIKE = re.compile(r"(^|_)(id|identifier|number|code|url|timestamp|date)($|_)")


def normalize_column_name(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "_", str(value).lower()).strip("_")
    return normalized or "column"


def _match_column(
    columns: Iterable[str], role: str, aliases: dict[str, list[str]] | None = None
) -> tuple[str | None, float]:
    normalized = {normalize_column_name(column): column for column in columns}
    candidates = tuple((aliases or {}).get(role, ROLE_CANDIDATES[role]))
    for index, candidate in enumerate(candidates):
        candidate = normalize_column_name(candidate)
        if candidate in normalized:
            return normalized[candidate], max(0.6, 1.0 - index * 0.04)
    return None, 0.0


def _numeric_candidates(frame: pd.DataFrame, excluded: set[str]) -> list[str]:
    candidates: list[str] = []
    for column in frame.columns:
        if column in excluded or ID_LIKE.search(normalize_column_name(column)):
            continue
        values = pd.to_numeric(frame[column], errors="coerce")
        if values.notna().mean() >= 0.8 and values.nunique(dropna=True) > 1:
            candidates.append(column)
    return candidates[:12]


def _infer_group(
    frame: pd.DataFrame,
    excluded: set[str],
    aliases: dict[str, list[str]] | None = None,
) -> tuple[str | None, float]:
    matched, confidence = _match_column(frame.columns, "group", aliases)
    if matched:
        return matched, confidence
    maximum_groups = max(20, min(250, int(np.sqrt(max(len(frame), 1)) * 4)))
    choices: list[tuple[float, str]] = []
    for column in frame.columns:
        if column in excluded:
            continue
        unique = frame[column].nunique(dropna=True)
        if 2 <= unique <= maximum_groups and unique < len(frame):
            repeated_share = 1.0 - unique / max(len(frame), 1)
            choices.append((repeated_share, column))
    if not choices:
        return None, 0.0
    return max(choices)[1], 0.45


def _json_safe_sample(frame: pd.DataFrame, limit: int = 5) -> list[dict[str, object]]:
    def safe_value(value: object) -> object:
        if isinstance(value, BaseGeometry):
            return value.wkt
        if isinstance(value, (pd.Timestamp, pd.Timedelta)):
            return str(value)
        if isinstance(value, np.generic):
            return value.item()
        missing = pd.isna(value)
        if isinstance(missing, (bool, np.bool_)) and missing:
            return None
        return value

    sample = frame.head(limit).map(safe_value)
    return json.loads(sample.to_json(orient="records", date_format="iso"))


def inspect_dataframe_schema(
    frame: pd.DataFrame, aliases: dict[str, list[str]] | None = None
) -> SchemaInspection:
    """Inspect a table and suggest a conservative semantic column mapping."""
    if frame.empty:
        raise DataValidationError("Cannot inspect an empty dataset")
    columns = [str(column) for column in frame.columns]
    target, target_confidence = _match_column(columns, "target", aliases)
    latitude, latitude_confidence = _match_column(columns, "latitude", aliases)
    longitude, longitude_confidence = _match_column(columns, "longitude", aliases)
    geometry, geometry_confidence = _match_column(columns, "geometry", aliases)
    identifier, id_confidence = _match_column(columns, "id", aliases)
    spatial_columns = {item for item in (latitude, longitude, geometry) if item}
    group, group_confidence = _infer_group(
        frame, spatial_columns | ({target} if target else set()), aliases
    )
    excluded = spatial_columns | {item for item in (target, group, identifier) if item}
    fixed_features = _numeric_candidates(frame, excluded)
    warnings: list[str] = []
    if target is None:
        warnings.append("A target variable could not be inferred; provide an explicit mapping.")
    if not ((latitude and longitude) or geometry):
        warnings.append(
            "Coordinates or a geometry column could not be inferred; provide an explicit mapping."
        )
    if group is None:
        warnings.append("A repeated geographic group could not be inferred.")
    if not fixed_features:
        warnings.append("No numeric fixed-effect features could be inferred.")
    mapping = None
    if target and group and fixed_features and ((latitude and longitude) or geometry):
        detected_crs = getattr(frame, "crs", None)
        mapping = DatasetColumnMapping(
            target_variable=target,
            group_col=group,
            fixed_features=fixed_features,
            lat_col=latitude if latitude and longitude else None,
            lon_col=longitude if latitude and longitude else None,
            geometry_col=None if latitude and longitude else geometry,
            id_col=identifier,
            source_crs=str(detected_crs) if detected_crs is not None else "EPSG:4326",
        )
    confidence = {
        "target_variable": target_confidence,
        "group_col": group_confidence,
        "location": min(latitude_confidence, longitude_confidence)
        if latitude and longitude
        else geometry_confidence,
        "id_col": id_confidence,
        "fixed_features": 0.7 if fixed_features else 0.0,
    }
    return SchemaInspection(
        columns=columns,
        row_count=len(frame),
        sample_rows=_json_safe_sample(frame),
        suggested_mapping=mapping,
        confidence=confidence,
        warnings=warnings,
    )


def _geometry_value(value: object) -> BaseGeometry:
    if isinstance(value, BaseGeometry):
        geometry = value
    elif isinstance(value, dict):
        geometry = shape(value)
    elif isinstance(value, str):
        geometry = wkt.loads(value)
    else:
        raise TypeError("unsupported geometry value")
    if geometry.is_empty:
        raise ValueError("empty geometry")
    return geometry if geometry.geom_type == "Point" else geometry.centroid


def _wgs84_coordinates(
    frame: pd.DataFrame, mapping: DatasetColumnMapping
) -> tuple[pd.Series, pd.Series]:
    if mapping.geometry_col:
        geometries = frame[mapping.geometry_col].map(_geometry_value)
        x = geometries.map(lambda geometry: geometry.x)
        y = geometries.map(lambda geometry: geometry.y)
    else:
        x = pd.to_numeric(frame[mapping.lon_col], errors="coerce")
        y = pd.to_numeric(frame[mapping.lat_col], errors="coerce")
    source = CRS.from_user_input(mapping.source_crs)
    if source != CRS.from_epsg(4326):
        transformer = Transformer.from_crs(source, 4326, always_xy=True)
        transformed = [transformer.transform(lon, lat) for lon, lat in zip(x, y, strict=True)]
        x = pd.Series((item[0] for item in transformed), index=frame.index, dtype=float)
        y = pd.Series((item[1] for item in transformed), index=frame.index, dtype=float)
    return y, x


def _safe_feature_names(source_columns: list[str]) -> dict[str, str]:
    used = {"record_id", "target", "latitude", "longitude", "group_id"}
    names: dict[str, str] = {}
    for source in source_columns:
        candidate = normalize_column_name(source)
        if candidate in used or candidate[0].isdigit():
            candidate = f"feature_{candidate}"
        base = candidate
        suffix = 2
        while candidate in used:
            candidate = f"{base}_{suffix}"
            suffix += 1
        names[source] = candidate
        used.add(candidate)
    return names


def standardize_dataset(
    frame: pd.DataFrame, column_mapping: DatasetColumnMapping | dict
) -> tuple[pd.DataFrame, list[str]]:
    """Convert arbitrary spatial data to a stable schema consumed by downstream tools."""
    mapping = (
        column_mapping
        if isinstance(column_mapping, DatasetColumnMapping)
        else DatasetColumnMapping.model_validate(column_mapping)
    )
    required = {
        mapping.target_variable,
        mapping.group_col,
        *mapping.fixed_features,
        *([mapping.geometry_col] if mapping.geometry_col else []),
        *([mapping.lat_col, mapping.lon_col] if mapping.lat_col else []),
        *([mapping.id_col] if mapping.id_col else []),
    }
    missing = sorted(column for column in required if column not in frame.columns)
    if missing:
        raise DataValidationError("Mapped source columns do not exist: " + ", ".join(missing))
    try:
        latitude, longitude = _wgs84_coordinates(frame, mapping)
    except (CRSError, GEOSException, ProjError, TypeError, ValueError) as exc:
        raise DataValidationError(f"Could not convert mapped geometry to WGS84: {exc}") from None
    feature_names = _safe_feature_names(mapping.fixed_features)
    standardized = pd.DataFrame(index=frame.index)
    standardized["record_id"] = (
        frame[mapping.id_col].astype(str)
        if mapping.id_col
        else [f"record-{index + 1}" for index in range(len(frame))]
    )
    standardized["target"] = frame[mapping.target_variable]
    standardized["latitude"] = latitude
    standardized["longitude"] = longitude
    standardized["group_id"] = frame[mapping.group_col].astype(str)
    for source, canonical in feature_names.items():
        standardized[canonical] = frame[source]
    standardized.attrs["source_mapping"] = mapping.model_dump()
    standardized.attrs["fixed_feature_mapping"] = feature_names
    return standardized, list(feature_names.values())
