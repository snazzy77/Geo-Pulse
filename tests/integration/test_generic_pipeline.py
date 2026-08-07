import json

import numpy as np
import pandas as pd

from geo_pulse.pipelines.analysis_pipeline import run_analysis
from geo_pulse.schemas.requests import SpatialAnalysisRequest


def test_generic_spatial_pipeline_auto_maps_and_publishes_schema(tmp_path, test_settings):
    index = np.arange(40)
    groups = np.repeat(["north", "south", "east", "west"], 10)
    exposure = 5.0 + index * 0.3
    income = 40.0 + (index % 10)
    group_effect = pd.Series(groups).map({"north": 1.0, "south": -0.5, "east": 0.4, "west": -0.2})
    frame = pd.DataFrame(
        {
            "record_id": [f"case-{item}" for item in index],
            "disease_rate": 2.0 + 0.7 * exposure - 0.03 * income + group_effect,
            "latitude": 41.85 + (index % 10) * 0.002,
            "longitude": -87.70 + (index // 10) * 0.003,
            "district": groups,
            "exposure": exposure,
            "income": income,
        }
    )
    source = tmp_path / "health.csv"
    frame.to_csv(source, index=False)
    test_settings.artifact_dir = tmp_path / "artifacts"

    request = SpatialAnalysisRequest(
        question="How is pollution exposure associated with disease rate?",
        data_path=source,
        target_transform="none",
    )
    response = run_analysis(request.to_analysis_request(), test_settings)

    assert response.status in {"completed", "completed-with-limitations"}
    assert "schema_manifest" in response.artifacts
    manifest = json.loads(
        __import__("pathlib").Path(response.artifacts["schema_manifest"]).read_text()
    )
    assert manifest["column_mapping"]["target_variable"] == "disease_rate"
    assert manifest["canonical_fixed_effects"] == ["exposure", "income"]
    assert manifest["analysis_crs"].startswith("EPSG:")
