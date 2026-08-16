from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path

from geo_pulse.core.config import Settings, load_settings
from geo_pulse.core.exceptions import DataValidationError
from geo_pulse.ingestion.osm_dataset import fetch_osm_place_dataset
from geo_pulse.schemas.sources import OSMPlaceDatasetRequest, SpatialDatasetResponse
from geo_pulse.storage.artifact_store import ArtifactStore
from geo_pulse.storage.dataset_store import DatasetStore


def _source_id(request: OSMPlaceDatasetRequest) -> str:
    identity = f"osm:{request.place.casefold()}:{request.feature_type}:{request.max_rows}"
    return hashlib.sha256(identity.encode()).hexdigest()[:12]


def resolve_osm_dataset_path(dataset_id: str, settings: Settings) -> Path:
    """Resolve an acquired OSM dataset without accepting arbitrary filesystem paths."""
    if re.fullmatch(r"[0-9a-f]{12}", dataset_id) is None:
        raise DataValidationError("OpenStreetMap dataset ID is invalid")
    path = settings.resolve(settings.data_dir) / "external" / "osm" / f"{dataset_id}.csv"
    if not path.is_file():
        raise DataValidationError("OpenStreetMap dataset was not found; fetch it again")
    return path


def acquire_osm_place_dataset(
    request: OSMPlaceDatasetRequest,
    settings: Settings | None = None,
) -> SpatialDatasetResponse:
    settings = settings or load_settings()
    dataset_id = _source_id(request)
    root = settings.resolve(settings.data_dir) / "external"
    relative_csv = f"osm/{dataset_id}.csv"
    manifest_name = f"{dataset_id}-manifest"
    csv_path = root / relative_csv
    manifest_path = root / "osm" / f"{manifest_name}.json"
    if csv_path.exists() and manifest_path.exists() and not request.refresh:
        frame = DatasetStore(root).read_csv(relative_csv)
        metadata = json.loads(manifest_path.read_text(encoding="utf-8"))
        return _response(dataset_id, frame, metadata, cached=True)
    osm_config = settings.data_sources.get("osm", {})
    frame, metadata = fetch_osm_place_dataset(
        request.place,
        request.feature_type,
        request.max_rows,
        settings.resolve(settings.cache_dir) / "osmnx",
        int(osm_config.get("dataset_request_timeout_s", 30)),
        float(osm_config.get("max_place_area_km2", 2500)),
        str(osm_config.get("http_user_agent", "Geo-Pulse/0.1 (local research application)")),
        settings.random_seed,
        list(
            osm_config.get(
                "overpass_endpoints",
                [
                    "https://overpass.private.coffee/api",
                    "https://overpass-api.de/api",
                ],
            )
        ),
        bool(osm_config.get("overpass_rate_limit", False)),
    )
    csv_path = DatasetStore(root).write_csv(frame, relative_csv)
    metadata = {
        **metadata,
        "dataset_id": dataset_id,
        "created_at": datetime.now(UTC).isoformat(),
        "local_path": str(csv_path.resolve()),
    }
    ArtifactStore(root).write_json("osm", manifest_name, metadata)
    return _response(dataset_id, frame, metadata, cached=False)


def _response(
    dataset_id: str,
    frame,
    metadata: dict[str, object],
    cached: bool,
) -> SpatialDatasetResponse:
    return SpatialDatasetResponse(
        dataset_id=dataset_id,
        provider="OpenStreetMap",
        place=str(metadata["place"]),
        feature_type=str(metadata["feature_type"]),
        row_count=len(frame),
        total_features_found=int(metadata["total_features_found"]),
        truncated=bool(metadata["truncated"]),
        columns=list(frame.columns),
        preview=json.loads(frame.head(5).to_json(orient="records")),
        local_path=str(metadata["local_path"]),
        download_url=f"/sources/osm/datasets/{dataset_id}/download",
        attribution=str(metadata["attribution"]),
        license_url=str(metadata["license_url"]),
        cached=cached,
    )
