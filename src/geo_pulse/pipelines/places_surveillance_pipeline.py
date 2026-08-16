from __future__ import annotations

import os

import numpy as np
import pandas as pd

from geo_pulse.agent.surveillance_agent import invoke_surveillance_agent
from geo_pulse.core.config import Settings, load_settings
from geo_pulse.core.exceptions import DataValidationError, ModelingError
from geo_pulse.core.run_context import RunContext
from geo_pulse.gis.exposure import calculate_industrial_exposure
from geo_pulse.ingestion.cdc_places_client import fetch_cdc_places_measure
from geo_pulse.ingestion.census_client import (
    HEALTH_CONTROL_COLUMNS,
    fetch_county_tract_boundaries,
    fetch_county_tract_demographics,
)
from geo_pulse.ingestion.osm_dataset import fetch_osm_place_dataset
from geo_pulse.modeling.model_registry import save_model
from geo_pulse.modeling.poisson_glm import fit_population_offset_poisson_glm
from geo_pulse.pipelines.health_surveillance_pipeline import (
    _build_health_report,
    _build_surveillance_map,
    _diagnose_counts,
)
from geo_pulse.reporting.policy_memo import build_policy_memo
from geo_pulse.schemas.reports import AnalysisResponse
from geo_pulse.schemas.requests import PlacesSurveillanceRequest
from geo_pulse.storage.artifact_store import ArtifactStore
from geo_pulse.storage.run_repository import RunRepository


def build_places_surveillance_matrix(
    request: PlacesSurveillanceRequest,
    settings: Settings,
) -> tuple[pd.DataFrame, list[str], dict[str, object]]:
    """Merge CDC PLACES, ACS demographics, TIGER tracts, and OSM industrial hazards."""
    census_config = settings.data_sources.get("census", {})
    census_key_name = str(census_config.get("api_key_env", "CENSUS_API_KEY"))
    census_key = os.getenv(census_key_name)
    cache_root = settings.resolve(settings.cache_dir)
    cdc_config = settings.data_sources.get("cdc_places", {})
    cdc, cdc_metadata = fetch_cdc_places_measure(
        request.county_fips,
        request.measure_id,
        cache_root / "cdc-places",
        app_token=os.getenv(str(cdc_config.get("app_token_env", "CDC_SOCRATA_APP_TOKEN"))),
    )
    demographics, census_year = fetch_county_tract_demographics(
        request.county_fips,
        request.demographic_controls,
        cache_root / "census",
        api_key=census_key,
    )
    tracts = fetch_county_tract_boundaries(request.county_fips, cache_root / "census")
    matrix = tracts.merge(demographics, on="tract_fips", how="inner", validate="one_to_one")
    matrix = matrix.merge(
        cdc.drop(columns=["latitude", "longitude"]),
        on="tract_fips",
        how="inner",
        validate="one_to_one",
    )
    if matrix.empty:
        raise DataValidationError(
            "CDC PLACES, Census demographics, and TIGER boundaries had no matching tract FIPS"
        )

    osm_config = settings.data_sources.get("osm", {})
    hazard_frames: list[pd.DataFrame] = []
    hazard_failures: list[str] = []
    hazard_metadata: list[dict[str, object]] = []
    for hazard_type in request.hazard_types:
        try:
            frame, metadata = fetch_osm_place_dataset(
                request.place,
                hazard_type,
                request.max_hazards_per_type,
                cache_root / "osmnx",
                int(osm_config.get("dataset_request_timeout_s", 30)),
                float(osm_config.get("max_place_area_km2", 2500)),
                str(osm_config.get("http_user_agent", "Geo-Pulse/0.1 research tool")),
                settings.random_seed,
                list(osm_config.get("overpass_endpoints", [])) or None,
                bool(osm_config.get("overpass_rate_limit", False)),
            )
            hazard_frames.append(frame)
            hazard_metadata.append(metadata)
        except DataValidationError as exc:
            hazard_failures.append(f"{hazard_type}: {exc}")
    if not hazard_frames:
        raise DataValidationError(
            "No OSM industrial hazards were available. " + " ".join(hazard_failures)
        )
    hazards = pd.concat(hazard_frames, ignore_index=True).drop_duplicates("record_id")
    matrix = calculate_industrial_exposure(
        matrix,
        hazards,
        request.buffer_m,
        settings.schema.get("aliases"),
    )
    matrix["target_y"] = pd.to_numeric(matrix["estimated_cases"], errors="coerce")
    matrix["group_id"] = matrix["county_fips"].astype(str)
    fixed_effects = ["industrial_exposure_score"] + [
        HEALTH_CONTROL_COLUMNS[control] for control in request.demographic_controls
    ]
    for column in fixed_effects:
        matrix[column] = pd.to_numeric(matrix[column], errors="coerce")
        matrix[column] = matrix[column].fillna(matrix[column].median())
    matrix["adult_population"] = pd.to_numeric(matrix["adult_population"], errors="coerce")
    matrix = matrix.dropna(
        subset=["target_y", "adult_population", "latitude", "longitude", *fixed_effects]
    )
    matrix = matrix[
        matrix["adult_population"].gt(0)
        & matrix["target_y"].ge(0)
        & np.isclose(matrix["target_y"], matrix["target_y"].round())
    ].reset_index(drop=True)
    minimum_rows = int(settings.models.get("minimum_rows", 20))
    if len(matrix) < minimum_rows:
        raise ModelingError(
            f"Live tract surveillance requires at least {minimum_rows} merged tracts; "
            f"found {len(matrix)}"
        )
    metadata: dict[str, object] = {
        "workflow": "live_cdc_places_census_osm",
        "cdc_places": cdc_metadata,
        "census_dataset": f"{census_year} ACS 5-year",
        "census_geography": "tract",
        "tigerweb_vintage": "current",
        "demographic_controls": request.demographic_controls,
        "osm_sources": hazard_metadata,
        "osm_failures": hazard_failures,
        "hazard_count": len(hazards),
        "buffer_m": request.buffer_m,
        "joined_tract_count": len(matrix),
        "target": "estimated_cases",
        "population_offset": "adult_population",
    }
    return matrix, fixed_effects, metadata


def run_places_surveillance(
    request: PlacesSurveillanceRequest,
    settings: Settings | None = None,
) -> AnalysisResponse:
    settings = settings or load_settings()
    artifact_root = request.output_dir or settings.artifacts
    repository = RunRepository(artifact_root / "run_metadata")
    context = RunContext(question=request.question)
    repository.save(context)
    try:
        context.transition("planning", "Prepared live federal surveillance plan")
        context.transition("ingesting", "Fetching CDC PLACES, Census, TIGERweb, and OSM data")
        matrix, fixed_effects, source_metadata = build_places_surveillance_matrix(request, settings)
        context.transition("engineering", "Merged sources by tract FIPS and calculated exposure")
        context.transition("modeling", "Fitting population-offset Poisson tract model")
        fitted, predictions, model_summary = fit_population_offset_poisson_glm(
            matrix,
            "target_y",
            fixed_effects,
            "adult_population",
            request.alert_threshold,
        )
        context.transition("diagnosing", "Detecting tract anomalies and residual clustering")
        diagnostic, warnings = _diagnose_counts(predictions, model_summary.converged, settings)
        alert_count = int(predictions["surveillance_alert"].sum())
        memo, actions = build_policy_memo(
            request.question, model_summary, diagnostic, alert_count, request.alert_threshold
        )
        base_limitations = [
            "CDC PLACES values are modeled small-area prevalence estimates, not observed case logs.",
            "Estimated case counts are prevalence multiplied by the adult population and rounded.",
            "The cross-sectional source releases are not evidence that industrial exposure caused illness.",
            "OSM completeness varies, and buffer overlap does not model emissions, wind, timing, or dose.",
            "PLACES documentation cautions against using estimates to evaluate local interventions.",
            *warnings,
        ]
        interpretation = invoke_surveillance_agent(
            request.question,
            model_summary,
            diagnostic,
            predictions,
            base_limitations=base_limitations,
        )
        findings = interpretation.findings
        limitations = interpretation.limitations
        summary = (
            f"Geo-Pulse merged live CDC PLACES, Census, TIGERweb, and OpenStreetMap data for "
            f"{len(predictions)} tracts with a population-offset Poisson model. "
            f"{interpretation.executive_summary}"
        )
        context.warnings.extend(warnings)
        context.transition("publishing", "Writing live surveillance matrix, map, and memo")
        store = ArtifactStore(artifact_root)
        map_path = store.path("maps", context.run_id, "html")
        report_path = store.path("reports", context.run_id, "html")
        predictions_path = store.path("diagnostics", f"{context.run_id}-predictions", "csv")
        matrix_path = store.path("datasets", f"{context.run_id}-surveillance-matrix", "csv")
        memo_path = store.path("reports", f"{context.run_id}-policy-memo", "txt")
        agent_report_path = store.path(
            "reports", f"{context.run_id}-epidemiology-agent", "md"
        )
        agent_payload_path = store.path(
            "run_metadata", f"{context.run_id}-epidemiology-agent-payload", "txt"
        )
        predictions.drop(columns=["geometry"], errors="ignore").to_csv(
            predictions_path, index=False
        )
        matrix.drop(columns=["geometry"], errors="ignore").to_csv(matrix_path, index=False)
        memo_path.write_text(memo, encoding="utf-8")
        agent_report_path.write_text(interpretation.markdown, encoding="utf-8")
        agent_payload_path.write_text(interpretation.agent_payload, encoding="utf-8")
        _build_surveillance_map(predictions, map_path)
        _build_health_report(request.question, interpretation, memo, map_path, report_path)
        model_path = store.path("models", context.run_id, "pkl")
        save_model(fitted.result, model_path)
        model_json = store.write_json(
            "models", f"{context.run_id}-summary", model_summary.model_dump()
        )
        diagnostic_json = store.write_json("diagnostics", context.run_id, diagnostic.model_dump())
        source_json = store.write_json("run_metadata", f"{context.run_id}-sources", source_metadata)
        memo_json = store.write_json(
            "reports",
            f"{context.run_id}-policy-memo",
            {"memo": memo, "recommended_actions": actions},
        )
        status = "completed" if diagnostic.passed else "completed-with-limitations"
        response = AnalysisResponse(
            run_id=context.run_id,
            status=status,
            summary=summary,
            findings=findings,
            limitations=limitations,
            artifacts={
                "map": str(map_path.resolve()),
                "report": str(report_path.resolve()),
                "model": str(model_path.resolve()),
                "model_summary": str(model_json.resolve()),
                "diagnostics": str(diagnostic_json.resolve()),
                "predictions": str(predictions_path.resolve()),
                "surveillance_matrix": str(matrix_path.resolve()),
                "source_manifest": str(source_json.resolve()),
                "policy_memo": str(memo_path.resolve()),
                "policy_memo_json": str(memo_json.resolve()),
                "epidemiology_agent_report": str(agent_report_path.resolve()),
                "epidemiology_agent_payload": str(agent_payload_path.resolve()),
            },
        )
        context.artifacts.update(response.artifacts)
        context.transition(status)
        repository.save(context)
        return response
    except Exception as exc:
        context.error = str(exc)
        context.transition("failed", str(exc))
        repository.save(context)
        raise
