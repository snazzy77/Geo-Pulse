from geo_pulse.agent.guardrails import validate_request_scope
from geo_pulse.agent.planner import create_plan
from geo_pulse.agent.state import AgentState
from geo_pulse.agent.tool_registry import default_tool_registry
from geo_pulse.core.config import Settings, load_settings
from geo_pulse.ingestion.property_loader import load_table
from geo_pulse.pipelines.analysis_pipeline import run_analysis
from geo_pulse.schemas.reports import AnalysisResponse
from geo_pulse.schemas.requests import AnalysisRequest


def execute(request: AnalysisRequest, settings: Settings | None = None) -> AnalysisResponse:
    validate_request_scope(request)
    state = AgentState(plan=create_plan(request))
    resolved_settings = settings or load_settings()
    if request.analysis_mode == "generic":
        inspector = default_tool_registry().get("inspect_dataframe_schema")
        inspection = inspector(
            load_table(request.property_path), resolved_settings.schema.get("aliases")
        )
        state.observations.append(
            {
                "tool": "inspect_dataframe_schema",
                "columns": inspection.columns,
                "row_count": inspection.row_count,
                "confidence": inspection.confidence,
                "warnings": inspection.warnings,
            }
        )
        if request.column_mapping is None and inspection.suggested_mapping is not None:
            request = request.model_copy(update={"column_mapping": inspection.suggested_mapping})
    response = run_analysis(request, resolved_settings)
    state.observations.append({"status": response.status, "run_id": response.run_id})
    state.completed = True
    return response
