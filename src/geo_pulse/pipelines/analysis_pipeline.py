from __future__ import annotations

import logging

from geo_pulse.core.config import Settings, load_settings
from geo_pulse.core.run_context import RunContext
from geo_pulse.diagnostics.diagnostic_runner import run_diagnostics
from geo_pulse.pipelines.correction_pipeline import run_correction_pipeline
from geo_pulse.pipelines.feature_pipeline import run_feature_pipeline
from geo_pulse.pipelines.ingestion_pipeline import run_ingestion
from geo_pulse.pipelines.modeling_pipeline import run_modeling_pipeline
from geo_pulse.pipelines.publishing_pipeline import run_publishing_pipeline
from geo_pulse.schemas.reports import AnalysisResponse
from geo_pulse.schemas.requests import AnalysisRequest
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
        fixed_effects = request.fixed_effects or list(settings.models.get("fixed_effects", []))
        context.transition("ingesting")
        properties, amenities = run_ingestion(
            request.property_path,
            request.amenity_path or settings.resolve(settings.data_sources["amenity_path"]),
            request.target,
            request.group_column,
        )
        context.transition("engineering")
        feature_frame, feature_set = run_feature_pipeline(properties, amenities, settings.features)
        context.stages[-1]["detail"] = f"Created {len(feature_set.columns)} documented features"
        context.transition("modeling")
        predictions, fitted, model_summary = run_modeling_pipeline(
            feature_frame, request.target, request.group_column, fixed_effects, settings.models
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
                feature_frame, request.target, request.group_column, fixed_effects, settings.models
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
            request.target,
            predictions,
            amenities,
            fitted,
            model_summary,
            diagnostic,
            artifact_root,
            context.warnings,
        )
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
