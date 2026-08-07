from geo_pulse.schemas.requests import AnalysisRequest


def create_plan(request: AnalysisRequest) -> dict:
    return {
        "question": request.question,
        "source": str(request.property_path),
        "target": request.target,
        "group_column": request.group_column,
        "steps": ["ingest", "engineer", "model", "diagnose", "correct-if-needed", "publish"],
    }
