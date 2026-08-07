import threading
import webbrowser
from pathlib import Path

import typer

from geo_pulse.agent.orchestrator import execute
from geo_pulse.agent.response_builder import as_text
from geo_pulse.core.config import load_settings
from geo_pulse.core.logging import configure_logging
from geo_pulse.pipelines.external_pipeline import run_external_analysis
from geo_pulse.schemas.external import ExternalAnalysisRequest
from geo_pulse.schemas.requests import AnalysisRequest

app = typer.Typer(help="Geo-Pulse real-estate spatial analytics")


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


@app.command()
def serve(
    host: str = "127.0.0.1",
    port: int = 8000,
    reload: bool = False,
    open_browser: bool = True,
) -> None:
    import uvicorn

    if open_browser and not reload:
        threading.Timer(1.0, lambda: webbrowser.open(f"http://{host}:{port}")).start()
    uvicorn.run("geo_pulse.api.app:app", host=host, port=port, reload=reload)


if __name__ == "__main__":
    app()
