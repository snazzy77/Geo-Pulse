from __future__ import annotations

import logging

import pandas as pd

from geo_pulse.core.config import Settings, load_settings
from geo_pulse.core.run_context import RunContext
from geo_pulse.diagnostics.diagnostic_runner import run_diagnostics
from geo_pulse.gis.crs import select_local_projected_crs
from geo_pulse.pipelines.correction_pipeline import run_correction_pipeline
from geo_pulse.pipelines.feature_pipeline import run_feature_pipeline
from geo_pulse.pipelines.ingestion_pipeline import run_ingestion, run_spatial_ingestion
from geo_pulse.pipelines.modeling_pipeline import run_modeling_pipeline
from geo_pulse.pipelines.publishing_pipeline import run_publishing_pipeline
from geo_pulse.schemas.reports import AnalysisResponse
from geo_pulse.schemas.requests import AnalysisRequest
from geo_pulse.storage.artifact_store import ArtifactStore
from geo_pulse.storage.run_repository import RunRepository

LOGGER = logging.getLogger(__name__)


def _diagnose(predictions, fixed_effects, model_summary, config, settings, can_retry):
    return run_diagnostics(
        predictions,
        fixed_effects,
        model_summary.converged,
        int(config.get("morans_k_neighbors", 5)),
        int(config.get("morans_permutations", 199)),
        float(config.get("morans_alpha", 0.05)),
        settings.random_seed,
        can_retry,
    )


def run_analysis(
    request: AnalysisRequest,
    settings: Settings | None = None,
) -> AnalysisResponse:
    settings = settings or load_settings()
    artifact_root = request.output_dir or settings.artifacts
    repository = RunRepository(artifact_root / "run_metadata")
    context = RunContext(question=request.question)
    repository.save(context)
    try:
        context.transition("planning", "Validated deterministic local analysis plan")
        context.transition("ingesting")
        schema_manifest = None
        if request.analysis_mode == "generic":
            ingested = run_spatial_ingestion(
                request.property_path,
                request.column_mapping,
                settings.schema.get("aliases"),
            )
            properties = ingested.frame
            fixed_effects = ingested.fixed_effects
            target = "target"
            group_column = "group_id"
            amenities = pd.DataFrame(
                columns=["amenity_id", "amenity_type", "latitude", "longitude"]
            )
            context.stages[-1]["detail"] = "Inspected and standardized arbitrary spatial schema"
            context.transition("engineering", "Using mapped numeric features")
            feature_frame = properties
            center_lat = float(properties["latitude"].mean())
            center_lon = float(properties["longitude"].mean())
            schema_manifest = {
                "source_columns": ingested.inspection.columns,
                "source_row_count": ingested.inspection.row_count,
                "column_mapping": ingested.mapping.model_dump(),
                "canonical_fixed_effects": fixed_effects,
                "inference_confidence": ingested.inspection.confidence,
                "inspection_warnings": ingested.inspection.warnings,
                "canonical_crs": "EPSG:4326",
                "analysis_crs": select_local_projected_crs(center_lat, center_lon).to_string(),
                "target_transform_requested": request.target_transform,
            }
        else:
            fixed_effects = request.fixed_effects or list(settings.models.get("fixed_effects", []))
            target = request.target
            group_column = request.group_column
            properties, amenities = run_ingestion(
                request.property_path,
                request.amenity_path or settings.resolve(settings.data_sources["amenity_path"]),
                target,
                group_column,
            )
            context.transition("engineering")
            feature_frame, feature_set = run_feature_pipeline(
                properties, amenities, settings.features
            )
            context.stages[-1]["detail"] = f"Created {len(feature_set.columns)} documented features"
        context.transition("modeling")
        predictions, fitted, model_summary = run_modeling_pipeline(
            feature_frame,
            target,
            group_column,
            fixed_effects,
            settings.models,
            request.target_transform,
        )
        maximum_attempts = int(settings.models.get("max_correction_attempts", 1))
        context.transition("diagnosing")
        diagnostic, warnings = _diagnose(
            predictions,
            fixed_effects,
            model_summary,
            settings.models,
            settings,
            maximum_attempts > 0,
        )
        warnings.extend(model_summary.extra.get("fit_warnings", []))
        attempts = 0
        while diagnostic.decision == "REVISE" and attempts < maximum_attempts:
            attempts += 1
            context.transition("correcting", f"Correction attempt {attempts}")
            feature_frame, fixed_effects, reason = run_correction_pipeline(
                feature_frame, fixed_effects
            )
            context.stages[-1]["detail"] = reason
            context.transition("modeling", f"Retraining after correction {attempts}")
            predictions, fitted, model_summary = run_modeling_pipeline(
                feature_frame,
                target,
                group_column,
                fixed_effects,
                settings.models,
                request.target_transform,
            )
            context.transition("diagnosing", f"Diagnostics after correction {attempts}")
            diagnostic, new_warnings = _diagnose(
                predictions,
                fixed_effects,
                model_summary,
                settings.models,
                settings,
                attempts < maximum_attempts,
            )
            warnings.extend(new_warnings)
            warnings.extend(model_summary.extra.get("fit_warnings", []))
        context.warnings.extend(dict.fromkeys(warnings))
        context.transition("publishing")
        response = run_publishing_pipeline(
            context.run_id,
            request.question,
            target,
            predictions,
            amenities,
            fitted,
            model_summary,
            diagnostic,
            artifact_root,
            context.warnings,
        )
        if schema_manifest is not None:
            schema_path = ArtifactStore(artifact_root).write_json(
                "run_metadata", f"{context.run_id}-schema", schema_manifest
            )
            response.artifacts["schema_manifest"] = str(schema_path.resolve())
        context.artifacts.update(response.artifacts)
        context.transition(response.status)
        repository.save(context)
        return response
    except Exception as exc:
        LOGGER.exception("Geo-Pulse run %s failed", context.run_id)
        context.error = str(exc)
        context.transition("failed", str(exc))
        repository.save(context)
        raise
