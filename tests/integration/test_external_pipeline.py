from pathlib import Path

import pandas as pd

from geo_pulse.pipelines import external_pipeline
from geo_pulse.schemas.external import ExternalAnalysisRequest
from geo_pulse.schemas.reports import AnalysisResponse


def test_external_pipeline_connects_kaggle_census_osm_and_model(
    monkeypatch, tmp_path, test_settings, sample_paths
):
    monkeypatch.setenv("CENSUS_API_KEY", "test-key")
    test_settings.data_dir = tmp_path / "data"
    test_settings.artifact_dir = tmp_path / "artifacts"
    properties = pd.read_csv(sample_paths[0])
    properties["postal_code"] = "78704"
    amenities = pd.read_csv(sample_paths[1])

    def fake_kaggle(*_args, **_kwargs):
        return properties, Path("austinHousingData.csv"), {"price": "latestPrice"}

    def fake_census(frame, *_args, **_kwargs):
        result = frame.copy()
        result["census_log_population"] = 10.0
        result["census_income_10k"] = 8.5
        result["census_home_value_100k"] = 4.5
        return result

    monkeypatch.setattr(external_pipeline, "acquire_kaggle_properties", fake_kaggle)
    monkeypatch.setattr(external_pipeline, "enrich_with_census", fake_census)
    monkeypatch.setattr(
        external_pipeline, "fetch_amenities_for_properties", lambda *_a, **_k: amenities
    )

    captured = {}

    def fake_analysis(request, _settings):
        captured["request"] = request
        return AnalysisResponse(run_id="external-test", status="completed", summary="ok")

    monkeypatch.setattr(external_pipeline, "run_analysis", fake_analysis)
    response = external_pipeline.run_external_analysis(
        ExternalAnalysisRequest(question="How do free spatial data affect prices?", max_rows=100),
        test_settings,
    )
    assert response.status == "completed"
    assert "census_income_10k" in captured["request"].fixed_effects
    assert Path(response.artifacts["source_manifest"]).exists()
