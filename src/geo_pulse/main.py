import threading
import webbrowser
from pathlib import Path

import typer

from geo_pulse.agent.orchestrator import execute
from geo_pulse.agent.response_builder import as_text
from geo_pulse.core.config import load_settings
from geo_pulse.core.logging import configure_logging
from geo_pulse.pipelines.external_pipeline import run_external_analysis
from geo_pulse.pipelines.health_surveillance_pipeline import run_health_surveillance
from geo_pulse.pipelines.places_surveillance_pipeline import run_places_surveillance
from geo_pulse.pipelines.source_acquisition_pipeline import acquire_osm_place_dataset
from geo_pulse.schemas.datasets import AnalysisKind, DatasetColumnMapping, TargetTransform
from geo_pulse.schemas.external import ExternalAnalysisRequest
from geo_pulse.schemas.requests import (
    AnalysisRequest,
    HealthAnalysisRequest,
    PlacesSurveillanceRequest,
    SpatialAnalysisRequest,
)
from geo_pulse.schemas.sources import OSMPlaceDatasetRequest

app = typer.Typer(help="Geo-Pulse general-purpose spatial analytics")


@app.command("analyze-health")
def analyze_health(
    outcomes: Path = typer.Option(..., exists=True, readable=True),
    hazards: Path = typer.Option(..., exists=True, readable=True),
    question: str = typer.Option(
        "How does proximity to industrial factories affect local asthma spikes?"
    ),
    buffer_m: float = typer.Option(2000, min=100, max=25_000),
    alert_threshold: float = typer.Option(2.0, min=1.0, max=5.0),
    demographic_control: list[str] | None = typer.Option(None),
    include_current_air_quality: bool = typer.Option(False),
    output_dir: Path | None = typer.Option(None),
    config_dir: Path = typer.Option(Path("configs"), exists=True, file_okay=False),
) -> None:
    """Run environmental-health count surveillance with a Poisson GLMM."""
    settings = load_settings(config_dir)
    configure_logging(settings.log_level)
    response = run_health_surveillance(
        HealthAnalysisRequest(
            question=question,
            outcome_path=outcomes,
            hazard_path=hazards,
            buffer_m=buffer_m,
            alert_threshold=alert_threshold,
            demographic_controls=demographic_control or [],
            include_current_air_quality=include_current_air_quality,
            output_dir=output_dir,
        ),
        settings,
    )
    typer.echo(as_text(response))


@app.command("analyze-places")
def analyze_places(
    place: str = typer.Option("Seattle, Washington, USA"),
    county_fips: str = typer.Option("53033", help="Five-digit state+county FIPS"),
    measure_id: str = typer.Option("CASTHMA", help="CDC PLACES measure ID"),
    question: str = typer.Option(
        "How is industrial proximity associated with modeled current asthma prevalence?"
    ),
    buffer_m: float = typer.Option(2000, min=100, max=25_000),
    alert_threshold: float = typer.Option(2.0, min=1.0, max=5.0),
    max_hazards_per_type: int = typer.Option(1000, min=1, max=5000),
    output_dir: Path | None = typer.Option(None),
    config_dir: Path = typer.Option(Path("configs"), exists=True, file_okay=False),
) -> None:
    """Run live CDC PLACES + Census + OpenStreetMap tract surveillance."""
    settings = load_settings(config_dir)
    configure_logging(settings.log_level)
    response = run_places_surveillance(
        PlacesSurveillanceRequest(
            question=question,
            place=place,
            county_fips=county_fips,
            measure_id=measure_id,
            buffer_m=buffer_m,
            alert_threshold=alert_threshold,
            max_hazards_per_type=max_hazards_per_type,
            output_dir=output_dir,
        ),
        settings,
    )
    typer.echo(as_text(response))


@app.command()
def analyze(
    question: str = typer.Option(..., help="Natural-language analysis question"),
    properties: Path = typer.Option(..., exists=True, readable=True),
    amenities: Path = typer.Option(..., exists=True, readable=True),
    target: str = typer.Option("price"),
    group: str = typer.Option("neighborhood"),
    output_dir: Path | None = typer.Option(None),
    config_dir: Path = typer.Option(Path("configs"), exists=True, file_okay=False),
) -> None:
    settings = load_settings(config_dir)
    configure_logging(settings.log_level)
    response = execute(
        AnalysisRequest(
            question=question,
            property_path=properties,
            amenity_path=amenities,
            target=target,
            group_column=group,
            output_dir=output_dir,
        ),
        settings,
    )
    typer.echo(as_text(response))


@app.command("analyze-free")
def analyze_free_sources(
    question: str = typer.Option("How does park distance affect home price?"),
    kaggle_dataset: str = typer.Option("ericpierce/austinhousingprices"),
    kaggle_filename: str = typer.Option("austinHousingData.csv"),
    census_year: int = typer.Option(2024),
    max_rows: int = typer.Option(500, min=20, max=5000),
    config_dir: Path = typer.Option(Path("configs"), exists=True, file_okay=False),
) -> None:
    settings = load_settings(config_dir)
    configure_logging(settings.log_level)
    response = run_external_analysis(
        ExternalAnalysisRequest(
            question=question,
            kaggle_dataset=kaggle_dataset,
            kaggle_filename=kaggle_filename,
            census_year=census_year,
            max_rows=max_rows,
        ),
        settings,
    )
    typer.echo(as_text(response))


@app.command("analyze-spatial")
def analyze_spatial(
    data: Path = typer.Option(..., exists=True, readable=True),
    question: str = typer.Option("What spatial factors are associated with the target?"),
    target_column: str | None = typer.Option(None),
    latitude_column: str | None = typer.Option(None),
    longitude_column: str | None = typer.Option(None),
    geometry_column: str | None = typer.Option(None),
    group_column: str | None = typer.Option(None),
    fixed_feature: list[str] | None = typer.Option(None),
    id_column: str | None = typer.Option(None),
    source_crs: str = typer.Option("EPSG:4326"),
    target_transform: TargetTransform = typer.Option("auto"),
    analysis_kind: AnalysisKind = typer.Option("auto", help="auto, explore, or model"),
    output_dir: Path | None = typer.Option(None),
    config_dir: Path = typer.Option(Path("configs"), exists=True, file_okay=False),
) -> None:
    supplied = any(
        value is not None
        for value in (
            target_column,
            latitude_column,
            longitude_column,
            geometry_column,
            group_column,
            fixed_feature,
            id_column,
        )
    )
    mapping = None
    if supplied:
        if not target_column or not group_column or not fixed_feature:
            raise typer.BadParameter(
                "Manual mapping requires --target-column, --group-column, and --fixed-feature"
            )
        mapping = DatasetColumnMapping(
            target_variable=target_column,
            lat_col=latitude_column,
            lon_col=longitude_column,
            geometry_col=geometry_column,
            group_col=group_column,
            fixed_features=fixed_feature,
            id_col=id_column,
            source_crs=source_crs,
        )
    settings = load_settings(config_dir)
    configure_logging(settings.log_level)
    request = SpatialAnalysisRequest(
        question=question,
        data_path=data,
        column_mapping=mapping,
        output_dir=output_dir,
        target_transform=target_transform,
        analysis_kind=analysis_kind,
    )
    typer.echo(as_text(execute(request.to_analysis_request(), settings)))


@app.command("fetch-osm")
def fetch_osm_dataset(
    place: str = typer.Option(..., help="City, borough, or district name"),
    feature_type: str = typer.Option(..., help="Feature key from the source-catalog command"),
    max_rows: int = typer.Option(1000, min=1, max=5000),
    refresh: bool = typer.Option(False),
    config_dir: Path = typer.Option(Path("configs"), exists=True, file_okay=False),
) -> None:
    settings = load_settings(config_dir)
    configure_logging(settings.log_level)
    result = acquire_osm_place_dataset(
        OSMPlaceDatasetRequest(
            place=place,
            feature_type=feature_type,
            max_rows=max_rows,
            refresh=refresh,
        ),
        settings,
    )
    typer.echo(
        f"Downloaded {result.row_count} {result.feature_type} records for "
        f"{result.place} to {result.local_path}"
    )


@app.command("source-catalog")
def source_catalog() -> None:
    from geo_pulse.ingestion.osm_dataset import osm_feature_catalog

    for feature in osm_feature_catalog():
        typer.echo(f"{feature.key:18} {feature.label} — {feature.description}")


def _run_dashboard(host: str, port: int, reload: bool, open_browser: bool) -> None:
    import uvicorn

    if open_browser and not reload:
        threading.Timer(1.0, lambda: webbrowser.open(f"http://{host}:{port}")).start()
    uvicorn.run("geo_pulse.api.app:app", host=host, port=port, reload=reload)


@app.command()
def dashboard(
    host: str = "127.0.0.1",
    port: int = 8000,
    reload: bool = False,
    open_browser: bool = True,
) -> None:
    """Start the Geo-Pulse web dashboard."""
    _run_dashboard(host, port, reload, open_browser)


@app.command()
def serve(
    host: str = "127.0.0.1",
    port: int = 8000,
    reload: bool = False,
    open_browser: bool = True,
) -> None:
    """Start the web dashboard (legacy alias for dashboard)."""
    _run_dashboard(host, port, reload, open_browser)


if __name__ == "__main__":
    app()
