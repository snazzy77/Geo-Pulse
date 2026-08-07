from geo_pulse.pipelines.analysis_pipeline import run_analysis
from geo_pulse.schemas.requests import AnalysisRequest


def test_end_to_end_pipeline_creates_artifacts(tmp_path, sample_paths, test_settings):
    response = run_analysis(
        AnalysisRequest(
            question="How does park distance affect home price?",
            property_path=sample_paths[0],
            amenity_path=sample_paths[1],
            output_dir=tmp_path / "artifacts",
        ),
        test_settings,
    )
    assert response.status in {"completed", "completed-with-limitations"}
    assert response.findings
    for path in response.artifacts.values():
        assert __import__("pathlib").Path(path).exists()
    report = __import__("pathlib").Path(response.artifacts["report"]).read_text(encoding="utf-8")
    assert f"../maps/{response.run_id}.html" in report
