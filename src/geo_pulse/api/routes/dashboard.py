from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter(include_in_schema=False)
TEMPLATE = Path(__file__).resolve().parents[1] / "templates" / "index.html"


@router.get("/", response_class=HTMLResponse)
def dashboard() -> HTMLResponse:
    return HTMLResponse(TEMPLATE.read_text(encoding="utf-8"))
