from __future__ import annotations

import html
import os
from pathlib import Path

import folium
import numpy as np
import pandas as pd
from folium.plugins import HeatMap
from scipy.spatial import cKDTree

from geo_pulse.core.config import Settings
from geo_pulse.core.run_context import RunContext
from geo_pulse.gis.crs import project_coordinates, select_local_projected_crs
from geo_pulse.ingestion.property_loader import load_table
from geo_pulse.ingestion.schema_mapper import standardize_spatial_locations
from geo_pulse.schemas.reports import AnalysisResponse
from geo_pulse.storage.artifact_store import ArtifactStore
from geo_pulse.storage.run_repository import RunRepository


def _categorical_summaries(frame: pd.DataFrame) -> dict[str, dict[str, int]]:
    excluded = {"record_id", "latitude", "longitude", "name", "operator", "osm_id"}
    summaries: dict[str, dict[str, int]] = {}
    for column in frame.columns:
        if column in excluded:
            continue
        unique = frame[column].nunique(dropna=True)
        if 1 <= unique <= 20 and not pd.api.types.is_numeric_dtype(frame[column]):
            summaries[column] = {
                str(key): int(value)
                for key, value in frame[column].fillna("Missing").value_counts().head(10).items()
            }
    return dict(list(summaries.items())[:5])


def _numeric_summaries(frame: pd.DataFrame) -> dict[str, dict[str, float]]:
    excluded = {"latitude", "longitude", "osm_id"}
    summaries: dict[str, dict[str, float]] = {}
    for column in frame.select_dtypes(include="number").columns:
        if column in excluded:
            continue
        values = pd.to_numeric(frame[column], errors="coerce").dropna()
        if len(values) < 2 or values.nunique() < 2:
            continue
        summaries[column] = {
            "mean": float(values.mean()),
            "median": float(values.median()),
            "minimum": float(values.min()),
            "maximum": float(values.max()),
        }
    return dict(list(summaries.items())[:10])


def _spatial_metrics(frame: pd.DataFrame) -> dict[str, object]:
    coordinates = frame[["latitude", "longitude"]].to_numpy(dtype=float)
    projected = project_coordinates(coordinates)
    west, south = float(frame["longitude"].min()), float(frame["latitude"].min())
    east, north = float(frame["longitude"].max()), float(frame["latitude"].max())
    width = float(np.ptp(projected[:, 0]))
    height = float(np.ptp(projected[:, 1]))
    area_km2 = max(width * height / 1_000_000, 0.0)
    metrics: dict[str, object] = {
        "record_count": len(frame),
        "centroid": {
            "latitude": float(frame["latitude"].mean()),
            "longitude": float(frame["longitude"].mean()),
        },
        "bounds": {"west": west, "south": south, "east": east, "north": north},
        "bounding_area_km2": area_km2,
        "density_per_km2": len(frame) / area_km2 if area_km2 > 0 else None,
    }
    if len(frame) >= 2:
        distances, _ = cKDTree(projected).query(projected, k=2)
        nearest = distances[:, 1]
        expected = 0.5 / np.sqrt(len(frame) / (area_km2 * 1_000_000)) if area_km2 > 0 else None
        ratio = float(nearest.mean() / expected) if expected else None
        pattern = (
            "clustered"
            if ratio is not None and ratio < 0.8
            else "dispersed"
            if ratio is not None and ratio > 1.2
            else "approximately random"
        )
        metrics.update(
            {
                "mean_nearest_neighbor_m": float(nearest.mean()),
                "median_nearest_neighbor_m": float(np.median(nearest)),
                "nearest_neighbor_ratio": ratio,
                "spatial_pattern": pattern,
            }
        )
    else:
        metrics.update(
            {
                "mean_nearest_neighbor_m": None,
                "median_nearest_neighbor_m": None,
                "nearest_neighbor_ratio": None,
                "spatial_pattern": "not estimable",
            }
        )
    bins = min(5, max(2, int(np.sqrt(len(frame)))))
    counts, lat_edges, lon_edges = np.histogram2d(
        frame["latitude"], frame["longitude"], bins=bins
    )
    hotspot = np.unravel_index(int(np.argmax(counts)), counts.shape)
    metrics["densest_grid_cell"] = {
        "count": int(counts[hotspot]),
        "latitude": float((lat_edges[hotspot[0]] + lat_edges[hotspot[0] + 1]) / 2),
        "longitude": float((lon_edges[hotspot[1]] + lon_edges[hotspot[1] + 1]) / 2),
    }
    return metrics


def _findings(
    question: str,
    metrics: dict[str, object],
    categories: dict[str, dict[str, int]],
    numeric: dict[str, dict[str, float]],
) -> list[str]:
    centroid = metrics["centroid"]
    findings = [
        (
            f"The dataset contains {metrics['record_count']:,} valid spatial records centered "
            f"near {centroid['latitude']:.4f}, {centroid['longitude']:.4f}."
        ),
    ]
    if metrics["mean_nearest_neighbor_m"] is not None:
        findings.append(
            f"The mean nearest-neighbor distance is {metrics['mean_nearest_neighbor_m']:,.0f} m "
            f"and the observed point pattern is {metrics['spatial_pattern']}."
        )
    hotspot = metrics["densest_grid_cell"]
    findings.append(
        f"The densest grid cell contains {hotspot['count']:,} records near "
        f"{hotspot['latitude']:.4f}, {hotspot['longitude']:.4f}."
    )
    for column, counts in list(categories.items())[:2]:
        leaders = ", ".join(f"{key}: {value}" for key, value in list(counts.items())[:5])
        findings.append(f"{column} distribution — {leaders}.")
    lower = question.lower()
    if any(term in lower for term in ("average", "mean", "median", "range")) and numeric:
        column, summary = next(iter(numeric.items()))
        findings.append(
            f"For {column}, the mean is {summary['mean']:,.3g}, median is "
            f"{summary['median']:,.3g}, and range is {summary['minimum']:,.3g}–"
            f"{summary['maximum']:,.3g}."
        )
    return findings


def _build_map(frame: pd.DataFrame, output: Path) -> None:
    center = [float(frame["latitude"].mean()), float(frame["longitude"].mean())]
    map_object = folium.Map(location=center, zoom_start=12, control_scale=True)
    points = folium.FeatureGroup(name="Spatial records", show=True)
    for _, row in frame.iterrows():
        label = row.get("name") or row.get("feature_type") or row.get("record_id")
        folium.CircleMarker(
            [float(row["latitude"]), float(row["longitude"])],
            radius=4,
            color="#2874a6",
            fill=True,
            fill_opacity=0.75,
            tooltip=html.escape(str(label)),
        ).add_to(points)
    points.add_to(map_object)
    if len(frame) >= 3:
        HeatMap(frame[["latitude", "longitude"]].values.tolist(), name="Density heatmap").add_to(
            map_object
        )
    folium.LayerControl(collapsed=False).add_to(map_object)
    map_object.fit_bounds(
        [
            [float(frame["latitude"].min()), float(frame["longitude"].min())],
            [float(frame["latitude"].max()), float(frame["longitude"].max())],
        ]
    )
    map_object.save(str(output))


def _build_report(
    question: str,
    summary: str,
    findings: list[str],
    limitations: list[str],
    metrics: dict[str, object],
    map_path: Path,
    report_path: Path,
) -> None:
    finding_items = "".join(f"<li>{html.escape(item)}</li>" for item in findings)
    limitation_items = "".join(f"<li>{html.escape(item)}</li>" for item in limitations)
    relative_map = Path(os.path.relpath(map_path, report_path.parent)).as_posix()
    report_path.write_text(
        "<!doctype html><html lang='en'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width'><title>Geo-Pulse report</title>"
        "<style>body{font-family:system-ui;max-width:960px;margin:2rem auto;padding:0 1rem;"
        "line-height:1.55}li{margin:.5rem 0}code{white-space:pre-wrap}</style></head><body>"
        f"<h1>Exploratory spatial analysis</h1><h2>Question</h2><p>{html.escape(question)}</p>"
        f"<p>{html.escape(summary)}</p><h2>Findings</h2><ul>{finding_items}</ul>"
        f"<h2>Spatial metrics</h2><pre>{html.escape(str(metrics))}</pre>"
        f"<h2>Limitations</h2><ul>{limitation_items}</ul>"
        f"<p><a href='{html.escape(relative_map)}'>Open interactive map</a></p></body></html>",
        encoding="utf-8",
    )


def run_exploratory_analysis(
    data_path: str | Path,
    question: str,
    settings: Settings,
    output_dir: Path | None = None,
) -> AnalysisResponse:
    artifact_root = output_dir or settings.artifacts
    repository = RunRepository(artifact_root / "run_metadata")
    context = RunContext(question=question)
    repository.save(context)
    try:
        context.transition("planning", "Selected general exploratory spatial analysis")
        context.transition("ingesting", "Loaded and normalized spatial records")
        source = load_table(data_path)
        frame, location_mapping = standardize_spatial_locations(
            source, settings.schema.get("aliases")
        )
        context.transition("engineering", "Computed distribution and proximity statistics")
        metrics = _spatial_metrics(frame)
        categories = _categorical_summaries(frame)
        numeric = _numeric_summaries(frame)
        metrics["categorical_summaries"] = categories
        metrics["numeric_summaries"] = numeric
        metrics["location_mapping"] = location_mapping
        metrics["analysis_crs"] = select_local_projected_crs(
            float(frame["latitude"].mean()), float(frame["longitude"].mean())
        ).to_string()
        context.transition("diagnosing", "Evaluated spacing, density, and grid hotspots")
        findings = _findings(question, metrics, categories, numeric)
        summary = (
            f"Geo-Pulse completed a general exploratory spatial analysis of "
            f"{len(frame):,} records. The point pattern is {metrics['spatial_pattern']}; "
            "use the map and findings to interpret the requested geographic question."
        )
        limitations = [
            "This is descriptive exploratory analysis and does not establish causality.",
            "Hotspots use a simple grid and may change with grid scale or incomplete source data.",
            "Nearest-neighbor classification is an approximate bounding-box comparison.",
        ]
        context.transition("publishing")
        store = ArtifactStore(artifact_root)
        map_path = store.path("maps", context.run_id, "html")
        report_path = store.path("reports", context.run_id, "html")
        data_output = store.path("diagnostics", f"{context.run_id}-records", "csv")
        frame.to_csv(data_output, index=False)
        _build_map(frame, map_path)
        _build_report(question, summary, findings, limitations, metrics, map_path, report_path)
        metrics_path = store.write_json("diagnostics", context.run_id, metrics)
        response = AnalysisResponse(
            run_id=context.run_id,
            status="completed",
            summary=summary,
            findings=findings,
            limitations=limitations,
            artifacts={
                "map": str(map_path.resolve()),
                "report": str(report_path.resolve()),
                "diagnostics": str(metrics_path.resolve()),
                "records": str(data_output.resolve()),
            },
        )
        context.artifacts.update(response.artifacts)
        context.transition("completed")
        repository.save(context)
        return response
    except Exception as exc:
        context.error = str(exc)
        context.transition("failed", str(exc))
        repository.save(context)
        raise
