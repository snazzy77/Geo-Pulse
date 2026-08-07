from __future__ import annotations

import os
from pathlib import Path

import pandas as pd

from geo_pulse.modeling.mixed_effects import FittedModel
from geo_pulse.modeling.model_registry import save_model
from geo_pulse.reporting.executive_summary import build_executive_summary
from geo_pulse.reporting.insight_generator import generate_findings
from geo_pulse.reporting.report_builder import build_report
from geo_pulse.schemas.models import DiagnosticSummary, ModelSummary
from geo_pulse.schemas.reports import AnalysisResponse
from geo_pulse.storage.artifact_store import ArtifactStore
from geo_pulse.visualization.charts import write_coefficient_table
from geo_pulse.visualization.map_builder import build_map

DEFAULT_LIMITATIONS = [
    "The analysis is observational and does not establish causality.",
    "Results depend on source-data completeness, accuracy, and geographic coverage.",
    "Reported performance is in-sample in this MVP and may overstate out-of-sample accuracy.",
    "Straight-line distance is used unless a network-distance adapter is configured.",
]


def run_publishing_pipeline(
    run_id: str,
    question: str,
    target: str,
    predictions: pd.DataFrame,
    amenities: pd.DataFrame,
    fitted: FittedModel,
    model: ModelSummary,
    diagnostic: DiagnosticSummary,
    artifact_root: str | Path,
    warnings: list[str],
) -> AnalysisResponse:
    store = ArtifactStore(artifact_root)
    map_path = store.path("maps", run_id, "html")
    report_path = store.path("reports", run_id, "html")
    prediction_path = store.path("diagnostics", f"{run_id}-predictions", "csv")
    coefficient_path = store.path("diagnostics", f"{run_id}-coefficients", "csv")
    model_path = store.path("models", run_id, "pkl")
    predictions.to_csv(prediction_path, index=False)
    write_coefficient_table(model, coefficient_path)
    save_model(fitted.result, model_path)
    build_map(predictions, amenities, target, map_path)
    findings = generate_findings(model, diagnostic)
    limitations = [*DEFAULT_LIMITATIONS, *warnings]
    summary = build_executive_summary(question, model, diagnostic)
    relative_map = Path(os.path.relpath(map_path, report_path.parent))
    build_report(
        question,
        summary,
        findings,
        limitations,
        model,
        diagnostic,
        relative_map,
        report_path,
    )
    model_json = store.write_json("models", f"{run_id}-summary", model.model_dump())
    diagnostic_json = store.write_json("diagnostics", run_id, diagnostic.model_dump())
    status = "completed" if diagnostic.passed else "completed-with-limitations"
    return AnalysisResponse(
        run_id=run_id,
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
            "predictions": str(prediction_path.resolve()),
            "coefficients": str(coefficient_path.resolve()),
        },
    )
