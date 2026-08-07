from __future__ import annotations

import hashlib
import os
from uuid import uuid4

from geo_pulse.core.config import Settings, load_settings
from geo_pulse.core.exceptions import DataValidationError
from geo_pulse.ingestion.census_client import enrich_with_census
from geo_pulse.ingestion.kaggle_source import acquire_kaggle_properties
from geo_pulse.ingestion.osm_client import fetch_amenities_for_properties
from geo_pulse.pipelines.analysis_pipeline import run_analysis
from geo_pulse.schemas.external import ExternalAnalysisRequest
from geo_pulse.schemas.reports import AnalysisResponse
from geo_pulse.schemas.requests import AnalysisRequest
from geo_pulse.storage.artifact_store import ArtifactStore

CENSUS_MODEL_FEATURES = [
    "census_log_population",
    "census_income_10k",
    "census_home_value_100k",
]


def run_external_analysis(
    request: ExternalAnalysisRequest,
    settings: Settings | None = None,
) -> AnalysisResponse:
    settings = settings or load_settings()
    source_id = uuid4().hex[:12]
    kaggle_config = settings.data_sources.get("kaggle", {})
    osm_config = settings.data_sources.get("osm", {})
    census_config = settings.data_sources.get("census", {})
    census_key_name = str(census_config.get("api_key_env", "CENSUS_API_KEY"))
    census_api_key = os.getenv(census_key_name)
    if not census_api_key:
        raise DataValidationError(
            f"Free public-data analysis requires {census_key_name}. Request a free Census API "
            "key at https://api.census.gov/data/key_signup.html and add it to .env."
        )
    column_mapping = request.column_mapping or kaggle_config.get("column_mapping")
    source_cache_id = hashlib.sha256(
        f"{request.kaggle_dataset}:{request.kaggle_filename}".encode()
    ).hexdigest()[:12]
    source_root = settings.resolve(settings.data_dir) / "raw" / "kaggle" / source_cache_id
    properties, source_path, resolved_mapping = acquire_kaggle_properties(
        request.kaggle_dataset,
        request.kaggle_filename,
        source_root,
        column_mapping,
        request.max_rows,
        settings.random_seed,
    )
    properties = enrich_with_census(
        properties,
        request.census_year,
        settings.resolve(settings.cache_dir) / "census",
        api_key=census_api_key,
        max_zip_codes=int(census_config.get("max_zip_codes", 100)),
    )
    amenities = fetch_amenities_for_properties(
        properties,
        list(settings.features.get("amenity_types", ["park", "school", "transit"])),
        buffer_m=float(osm_config.get("buffer_m", 1500)),
        cache_dir=settings.resolve(settings.cache_dir) / "osmnx",
        request_timeout_s=int(osm_config.get("request_timeout_s", 180)),
        max_bbox_area_km2=float(osm_config.get("max_bbox_area_km2", 5000)),
    )
    interim = settings.resolve(settings.data_dir) / "interim" / source_id
    interim.mkdir(parents=True, exist_ok=False)
    property_path = interim / "properties.csv"
    amenity_path = interim / "amenities.csv"
    properties.to_csv(property_path, index=False)
    amenities.to_csv(amenity_path, index=False)
    fixed_effects = list(settings.models.get("fixed_effects", []))
    fixed_effects.extend(
        feature for feature in CENSUS_MODEL_FEATURES if feature not in fixed_effects
    )
    response = run_analysis(
        AnalysisRequest(
            question=request.question,
            property_path=property_path,
            amenity_path=amenity_path,
            fixed_effects=fixed_effects,
        ),
        settings,
    )
    manifest = {
        "kaggle_dataset": request.kaggle_dataset,
        "kaggle_filename": request.kaggle_filename,
        "downloaded_file": str(source_path),
        "column_mapping": resolved_mapping,
        "property_rows": len(properties),
        "osm_amenity_rows": len(amenities),
        "osm_amenity_types": sorted(amenities["amenity_type"].unique()),
        "census_dataset": f"{request.census_year} ACS 5-year",
        "census_variables": CENSUS_MODEL_FEATURES,
    }
    manifest_path = ArtifactStore(settings.artifacts).write_json(
        "run_metadata", f"{response.run_id}-sources", manifest
    )
    response.artifacts["source_manifest"] = str(manifest_path.resolve())
    return response
