from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from geo_pulse import __version__
from geo_pulse.api.error_handlers import register_error_handlers
from geo_pulse.api.routes import analyses, dashboard, datasets, health, models, reports, sources

app = FastAPI(
    title="Geo-Pulse API",
    description="Real-estate spatial analytics with mixed-effects modeling and diagnostics",
    version=__version__,
)
STATIC_DIR = Path(__file__).resolve().parent / "static"
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
app.include_router(dashboard.router)
app.include_router(health.router)
app.include_router(analyses.router)
app.include_router(datasets.router)
app.include_router(models.router)
app.include_router(reports.router)
app.include_router(sources.router)
register_error_handlers(app)
