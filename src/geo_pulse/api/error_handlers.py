from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from geo_pulse.core.exceptions import GeoPulseError


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(GeoPulseError)
    async def geo_pulse_error(_: Request, exc: GeoPulseError) -> JSONResponse:
        return JSONResponse(
            status_code=422, content={"error": type(exc).__name__, "detail": str(exc)}
        )
