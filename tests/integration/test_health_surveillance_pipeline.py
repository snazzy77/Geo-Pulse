from pathlib import Path

from geo_pulse.pipelines.health_surveillance_pipeline import run_health_surveillance
from geo_pulse.sample_data import generate_health_sample_data
from geo_pulse.schemas.requests import HealthAnalysisRequest


def test_health_pipeline_publishes_poisson_surveillance_and_policy_memo(
    tmp_path, test_settings
):
    outcomes, hazards = generate_health_sample_data(tmp_path / "sources", seed=42)
    test_settings.artifact_dir = tmp_path / "artifacts"

    response = run_health_surveillance(
        HealthAnalysisRequest(
            question="How does industrial exposure affect local asthma spikes?",
            outcome_path=outcomes,
            hazard_path=hazards,
            buffer_m=2000,
        ),
        test_settings,
    )

    assert response.status in {"completed", "completed-with-limitations"}
    assert "Poisson GLMM" in response.summary
    assert {
        "map",
        "report",
        "model_summary",
        "diagnostics",
        "predictions",
        "policy_memo",
        "epidemiology_agent_report",
        "epidemiology_agent_payload",
    } <= response.artifacts.keys()
    memo = Path(response.artifacts["policy_memo"]).read_text(encoding="utf-8")
    assert "PUBLIC HEALTH SURVEILLANCE MEMO" in memo
    assert "Recommended actions" in memo
    report = Path(response.artifacts["report"]).read_text(encoding="utf-8")
    assert "Executive Summary" in report
    assert "Environmental Exposure Evaluation" in report
    assert "Socioeconomic Vulnerability Analysis" in report
    assert "Surveillance Recommendations" in report
    agent_markdown = Path(response.artifacts["epidemiology_agent_report"]).read_text(
        encoding="utf-8"
    )
    assert "## Findings" in agent_markdown
    assert "## Limitations" in agent_markdown
