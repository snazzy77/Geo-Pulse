from geo_pulse.schemas.requests import AnalysisRequest


def create_plan(request: AnalysisRequest) -> dict:
    steps = (
        ["inspect-schema", "standardize", "project", "model", "diagnose", "publish"]
        if request.analysis_mode == "generic"
        else ["ingest", "engineer", "model", "diagnose", "correct-if-needed", "publish"]
    )
    return {
        "question": request.question,
        "source": str(request.property_path),
        "target": request.target,
        "group_column": request.group_column,
        "analysis_mode": request.analysis_mode,
        "steps": steps,
    }
