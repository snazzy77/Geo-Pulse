from geo_pulse.agent.guardrails import validate_request_scope
from geo_pulse.agent.planner import create_plan
from geo_pulse.agent.state import AgentState
from geo_pulse.core.config import Settings
from geo_pulse.pipelines.analysis_pipeline import run_analysis
from geo_pulse.schemas.reports import AnalysisResponse
from geo_pulse.schemas.requests import AnalysisRequest


def execute(request: AnalysisRequest, settings: Settings | None = None) -> AnalysisResponse:
    validate_request_scope(request)
    state = AgentState(plan=create_plan(request))
    response = run_analysis(request, settings)
    state.observations.append({"status": response.status, "run_id": response.run_id})
    state.completed = True
    return response
