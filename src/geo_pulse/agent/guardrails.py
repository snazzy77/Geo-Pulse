from geo_pulse.core.exceptions import DataValidationError
from geo_pulse.schemas.requests import AnalysisRequest


def validate_request_scope(request: AnalysisRequest) -> None:
    lower = request.question.lower()
    if any(term in lower for term in ("guarantee", "risk-free", "certain profit")):
        raise DataValidationError("Geo-Pulse cannot provide guaranteed investment outcomes")
