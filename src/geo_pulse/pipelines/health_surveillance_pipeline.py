from __future__ import annotations

import html
import os
from pathlib import Path

import folium
import numpy as np
import pandas as pd

from geo_pulse.agent.surveillance_agent import (
    SurveillanceAgentOutput,
    invoke_surveillance_agent,
)
from geo_pulse.core.config import Settings, load_settings
from geo_pulse.core.exceptions import DataValidationError, ModelingError
from geo_pulse.core.run_context import RunContext
from geo_pulse.diagnostics.morans_i import morans_i
from geo_pulse.gis.exposure import calculate_industrial_exposure
from geo_pulse.gis.geometries import coordinate_array
from geo_pulse.gis.spatial_weights import knn_weights
from geo_pulse.ingestion.census_client import enrich_health_with_census
from geo_pulse.ingestion.open_meteo_air_quality import fetch_current_air_quality
from geo_pulse.ingestion.property_loader import load_table
from geo_pulse.ingestion.schema_mapper import inspect_dataframe_schema, standardize_dataset
from geo_pulse.modeling.model_registry import save_model
from geo_pulse.modeling.poisson_glmm import fit_poisson_glmm
from geo_pulse.reporting.policy_memo import build_policy_memo
from geo_pulse.schemas.models import DiagnosticSummary
from geo_pulse.schemas.reports import AnalysisResponse
from geo_pulse.schemas.requests import HealthAnalysisRequest
from geo_pulse.storage.artifact_store import ArtifactStore
from geo_pulse.storage.run_repository import RunRepository


def _prepare_health_data(
    request: HealthAnalysisRequest, settings: Settings
) -> tuple[pd.DataFrame, list[str], dict[str, object]]:
    outcomes = load_table(request.outcome_path)
    hazards = load_table(request.hazard_path)
    census_year = None
    if request.demographic_controls:
        census_config = settings.data_sources.get("census", {})
        census_key_name = str(census_config.get("api_key_env", "CENSUS_API_KEY"))
        outcomes, census_year = enrich_health_with_census(
            outcomes,
            request.demographic_controls,
            settings.resolve(settings.cache_dir) / "census",
            api_key=os.getenv(census_key_name),
            max_zip_codes=int(census_config.get("max_zip_codes", 100)),
        )
    exposed = calculate_industrial_exposure(
        outcomes,
        hazards,
        request.buffer_m,
        settings.schema.get("aliases"),
    )
    exposure_metadata = dict(exposed.attrs)
    if census_year is not None:
        exposure_metadata["census_dataset"] = f"{census_year} ACS 5-year"
        exposure_metadata["demographic_controls"] = request.demographic_controls
    if request.include_current_air_quality:
        exposed = fetch_current_air_quality(exposed)
        exposure_metadata["air_quality_provider"] = "Open-Meteo"
        exposure_metadata["air_quality_temporal_basis"] = "current conditions at analysis time"
    inspection = inspect_dataframe_schema(exposed, settings.schema.get("aliases"))
    mapping = request.column_mapping or inspection.suggested_mapping
    if mapping is None:
        details = " ".join(inspection.warnings)
        raise DataValidationError(
            "Could not infer the health target, geographic group, and covariates. " + details
        )
    standardized, fixed_effects = standardize_dataset(exposed, mapping)
    standardized = standardized.rename(columns={"target": "target_y"})
    standardized["target_y"] = pd.to_numeric(standardized["target_y"], errors="coerce")
    for column in fixed_effects:
        standardized[column] = pd.to_numeric(standardized[column], errors="coerce")
        standardized[column] = standardized[column].fillna(standardized[column].median())
    standardized = standardized.dropna(
        subset=["target_y", "latitude", "longitude", "group_id", *fixed_effects]
    )
    standardized = standardized[
        standardized["target_y"].ge(0)
        & np.isclose(standardized["target_y"], standardized["target_y"].round())
    ].reset_index(drop=True)
    minimum_rows = int(settings.models.get("minimum_rows", 20))
    minimum_groups = int(settings.models.get("minimum_groups", 2))
    minimum_per_group = int(settings.models.get("minimum_rows_per_group", 2))
    group_sizes = standardized["group_id"].value_counts()
    standardized = standardized[
        standardized["group_id"].isin(group_sizes[group_sizes >= minimum_per_group].index)
    ].reset_index(drop=True)
    if len(standardized) < minimum_rows:
        raise ModelingError(
            f"Poisson surveillance model requires at least {minimum_rows} valid count rows; "
            f"found {len(standardized)}"
        )
    if standardized["group_id"].nunique() < minimum_groups:
        raise ModelingError(
            f"Poisson surveillance model requires at least {minimum_groups} geographic groups"
        )
    metadata = {
        **exposure_metadata,
        "source_columns": inspection.columns,
        "column_mapping": mapping.model_dump(),
        "canonical_target": "target_y",
        "canonical_fixed_effects": fixed_effects,
        "inspection_warnings": inspection.warnings,
    }
    return standardized, fixed_effects, metadata


def _diagnose_counts(
    predictions: pd.DataFrame, converged: bool, settings: Settings
) -> tuple[DiagnosticSummary, list[str]]:
    permutations = int(settings.models.get("morans_permutations", 199))
    alpha = float(settings.models.get("morans_alpha", 0.05))
    weights = knn_weights(
        coordinate_array(predictions), int(settings.models.get("morans_k_neighbors", 5))
    )
    result = morans_i(
        predictions["pearson_residual"].to_numpy(dtype=float),
        weights,
        permutations,
        settings.random_seed,
    )
    warnings: list[str] = []
    mean_count = float(predictions["target_y"].mean())
    variance = float(predictions["target_y"].var())
    if mean_count > 0 and variance > 1.5 * mean_count:
        warnings.append(
            "Outcome variance substantially exceeds its mean; assess negative-binomial or "
            "zero-inflated sensitivity models before operational decisions."
        )
    passed = converged and result.p_value >= alpha
    return (
        DiagnosticSummary(
            morans_i=result.statistic,
            expected_i=result.expected,
            p_value=result.p_value,
            permutations=result.permutations,
            passed=passed,
            decision="PASS" if passed else "REVIEW",
        ),
        warnings,
    )


def _build_surveillance_map(predictions: pd.DataFrame, output_path: Path) -> None:
    center = [float(predictions["latitude"].mean()), float(predictions["longitude"].mean())]
    map_object = folium.Map(location=center, zoom_start=11, control_scale=True)
    layer = folium.FeatureGroup(name="Respiratory surveillance", show=True)
    for _, row in predictions.iterrows():
        alert = bool(row["surveillance_alert"])
        exposure = int(row.get("industrial_exposure_score", 0))
        color = "#d73027" if alert else "#fc8d59" if exposure > 0 else "#4575b4"
        tooltip = (
            f"Record: {html.escape(str(row['record_id']))}<br>"
            f"Cases: {float(row['target_y']):,.0f}<br>"
            f"Expected: {float(row['predicted_target_y']):,.1f}<br>"
            f"Industrial exposure score: {exposure}<br>"
            f"Alert: {'Yes' if alert else 'No'}"
        )
        folium.CircleMarker(
            [float(row["latitude"]), float(row["longitude"])],
            radius=8 if alert else 5,
            color=color,
            fill=True,
            fill_opacity=0.8,
            tooltip=tooltip,
        ).add_to(layer)
    layer.add_to(map_object)
    folium.LayerControl(collapsed=False).add_to(map_object)
    map_object.save(str(output_path))


def _build_health_report(
    question: str,
    interpretation: SurveillanceAgentOutput,
    memo: str,
    map_path: Path,
    report_path: Path,
) -> None:
    relative_map = Path(os.path.relpath(map_path, report_path.parent)).as_posix()
    finding_html = "".join(
        f"<li>{html.escape(item)}</li>" for item in interpretation.findings
    )
    limitation_html = "".join(
        f"<li>{html.escape(item)}</li>" for item in interpretation.limitations
    )
    recommendation_html = "".join(
        f"<li>{html.escape(item)}</li>"
        for item in interpretation.surveillance_recommendations
    )
    outlier_rows = "".join(
        "<tr>"
        f"<td>{html.escape(str(item['geography']))}</td>"
        f"<td>{float(item['pearson_residual']):.2f}</td>"
        f"<td>{float(item.get('observed', float('nan'))):.1f}</td>"
        f"<td>{float(item.get('expected', float('nan'))):.1f}</td>"
        "</tr>"
        for item in interpretation.top_outliers
    )
    outlier_table = (
        "<table><thead><tr><th>Geography</th><th>Pearson residual</th>"
        "<th>Observed</th><th>Expected</th></tr></thead>"
        f"<tbody>{outlier_rows}</tbody></table>"
        if outlier_rows
        else "<p>No named positive-residual geography was available.</p>"
    )
    report_path.write_text(
        "<!doctype html><html lang='en'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width'><title>Geo-Pulse surveillance report</title>"
        "<style>:root{color-scheme:dark;--cyan:#00f6ff;--blue:#168cff;--ink:#e9fbff;"
        "--muted:#83a8b5;--line:#164458;--panel:#07131b}*{box-sizing:border-box}"
        "body{font-family:Inter,system-ui,sans-serif;max-width:1040px;margin:0 auto;padding:3rem 1.4rem;"
        "line-height:1.62;color:var(--ink);background:#010609}h1{font-size:2.7rem;line-height:1.05}"
        "h2{margin-top:2.4rem;color:var(--cyan);border-bottom:1px solid var(--line);padding-bottom:.45rem}"
        "p,li{color:#c8e1e8}.summary,.memo{padding:1.15rem 1.3rem;background:var(--panel);"
        "border:1px solid var(--line);border-left:4px solid var(--cyan);border-radius:8px}"
        ".memo{white-space:pre-wrap}table{border-collapse:collapse;width:100%;background:var(--panel)}"
        "th,td{border:1px solid var(--line);padding:.65rem;text-align:left}th{color:var(--cyan)}"
        "a{display:inline-block;margin-top:1.2rem;padding:.75rem 1rem;color:#001116;background:var(--cyan);"
        "border-radius:8px;text-decoration:none;font-weight:750}</style></head><body>"
        "<p style='color:var(--cyan);letter-spacing:.14em;font-weight:800'>GEO-PULSE · SURVEILLANCE REPORT</p>"
        f"<h1>Environmental Health Risk Assessment</h1><h2>Research Question</h2>"
        f"<p>{html.escape(question)}</p><h2>Executive Summary</h2>"
        f"<div class='summary'>{html.escape(interpretation.executive_summary)}</div>"
        f"<h2>Environmental Exposure Evaluation</h2><p>{html.escape(interpretation.environmental_exposure_evaluation)}</p>"
        f"<h2>Socioeconomic Vulnerability Analysis</h2><p>{html.escape(interpretation.socioeconomic_vulnerability_analysis)}</p>"
        f"<h2>Spatial Diagnostics and Anomalous Geographies</h2><p>{html.escape(interpretation.spatial_diagnostics)}</p>"
        f"{outlier_table}<h2>Surveillance Recommendations</h2><ul>{recommendation_html}</ul>"
        f"<h2>Findings</h2><ul>{finding_html}</ul><h2>Limitations</h2>"
        f"<ul>{limitation_html}</ul><h2>Public Health Memo</h2>"
        f"<div class='memo'>{html.escape(memo)}</div><a href='{html.escape(relative_map)}'>"
        "Open surveillance map</a></body></html>",
        encoding="utf-8",
    )


def run_health_surveillance(
    request: HealthAnalysisRequest,
    settings: Settings | None = None,
) -> AnalysisResponse:
    settings = settings or load_settings()
    artifact_root = request.output_dir or settings.artifacts
    repository = RunRepository(artifact_root / "run_metadata")
    context = RunContext(question=request.question)
    repository.save(context)
    try:
        context.transition("planning", "Prepared epidemiological surveillance plan")
        context.transition("ingesting", "Loaded health outcomes and environmental hazards")
        dataset, fixed_effects, schema_metadata = _prepare_health_data(request, settings)
        context.transition(
            "engineering",
            f"Calculated {request.buffer_m:,.0f} m industrial buffer exposure scores",
        )
        context.transition("modeling", "Fitting Poisson GLMM for non-negative count outcomes")
        fitted, predictions, model_summary = fit_poisson_glmm(
            dataset,
            "target_y",
            "group_id",
            fixed_effects,
            request.alert_threshold,
        )
        context.transition("diagnosing", "Checking count anomalies and residual spatial clustering")
        diagnostic, warnings = _diagnose_counts(predictions, model_summary.converged, settings)
        alert_count = int(predictions["surveillance_alert"].sum())
        memo, actions = build_policy_memo(
            request.question,
            model_summary,
            diagnostic,
            alert_count,
            request.alert_threshold,
        )
        base_limitations = [
            "Associations are observational and do not prove industrial exposure caused illness.",
            "Buffer overlap is a screening proxy and does not model emissions, wind, or dose.",
            "Surveillance alerts require validation against reporting delays and case definitions.",
            *(
                [
                    (
                        "Current Open-Meteo readings may not align temporally with historical "
                        "health outcomes."
                    )
                ]
                if request.include_current_air_quality
                else []
            ),
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
            f"Geo-Pulse analyzed {len(predictions)} health observations across "
            f"{predictions['group_id'].nunique()} geographic groups with a Poisson GLMM. "
            f"{interpretation.executive_summary}"
        )
        context.warnings.extend(warnings)
        context.transition("publishing", "Writing surveillance map and policy memo")
        store = ArtifactStore(artifact_root)
        map_path = store.path("maps", context.run_id, "html")
        report_path = store.path("reports", context.run_id, "html")
        predictions_path = store.path("diagnostics", f"{context.run_id}-predictions", "csv")
        memo_path = store.path("reports", f"{context.run_id}-policy-memo", "txt")
        agent_report_path = store.path(
            "reports", f"{context.run_id}-epidemiology-agent", "md"
        )
        agent_payload_path = store.path(
            "run_metadata", f"{context.run_id}-epidemiology-agent-payload", "txt"
        )
        predictions.to_csv(predictions_path, index=False)
        memo_path.write_text(memo, encoding="utf-8")
        agent_report_path.write_text(interpretation.markdown, encoding="utf-8")
        agent_payload_path.write_text(interpretation.agent_payload, encoding="utf-8")
        _build_surveillance_map(predictions, map_path)
        _build_health_report(request.question, interpretation, memo, map_path, report_path)
        model_path = store.path("models", context.run_id, "pkl")
        save_model(fitted.result, model_path)
        model_json = store.write_json("models", f"{context.run_id}-summary", model_summary.model_dump())
        diagnostic_json = store.write_json("diagnostics", context.run_id, diagnostic.model_dump())
        schema_json = store.write_json("run_metadata", f"{context.run_id}-schema", schema_metadata)
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
                "schema_manifest": str(schema_json.resolve()),
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
