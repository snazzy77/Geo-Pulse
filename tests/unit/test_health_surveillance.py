import numpy as np
import pandas as pd

from geo_pulse.gis.exposure import calculate_industrial_exposure
from geo_pulse.ingestion.open_meteo_air_quality import fetch_current_air_quality
from geo_pulse.modeling.poisson_glm import fit_population_offset_poisson_glm
from geo_pulse.modeling.poisson_glmm import fit_poisson_glmm


def test_industrial_buffers_create_exposure_scores_and_nearest_distance():
    outcomes = pd.DataFrame(
        {
            "record_id": ["tract-a", "tract-b", "tract-c"],
            "latitude": [47.600, 47.615, 47.700],
            "longitude": [-122.300, -122.300, -122.300],
        }
    )
    hazards = pd.DataFrame(
        {
            "record_id": ["factory-1"],
            "latitude": [47.600],
            "longitude": [-122.300],
        }
    )

    result = calculate_industrial_exposure(outcomes, hazards, buffer_m=2000)

    assert result["industrial_exposure_score"].tolist() == [1, 1, 0]
    assert result.loc[0, "nearest_industrial_site_km"] < 0.01
    assert result.loc[2, "nearest_industrial_site_km"] > 10


def test_poisson_glmm_models_counts_and_flags_positive_anomalies():
    rng = np.random.default_rng(7)
    exposure = np.tile([0, 1, 2], 24)
    groups = np.repeat(["a", "b", "c", "d"], 18)
    expected = np.exp(1.1 + 0.25 * exposure)
    frame = pd.DataFrame(
        {
            "target_y": rng.poisson(expected),
            "group_id": groups,
            "industrial_exposure_score": exposure,
            "latitude": 40 + rng.normal(0, 0.02, len(groups)),
            "longitude": -75 + rng.normal(0, 0.02, len(groups)),
        }
    )

    _, predictions, summary = fit_poisson_glmm(
        frame,
        "target_y",
        "group_id",
        ["industrial_exposure_score"],
        alert_threshold=1.5,
    )

    assert summary.model_type.startswith("Bayesian Poisson GLMM")
    assert summary.extra["family"] == "Poisson"
    assert predictions["predicted_target_y"].gt(0).all()
    assert predictions["surveillance_alert"].dtype == bool
    assert predictions["surveillance_alert"].equals(predictions["pearson_residual"] >= 1.5)


def test_poisson_glm_uses_population_offset_for_tract_rates():
    rng = np.random.default_rng(19)
    population = np.linspace(700, 5000, 60).astype(int)
    exposure = np.tile([0, 1, 2], 20)
    expected = population * np.exp(-3.0 + 0.15 * exposure)
    frame = pd.DataFrame(
        {
            "target_y": rng.poisson(expected),
            "adult_population": population,
            "industrial_exposure_score": exposure,
            "county_fips": "53033",
        }
    )

    _, predictions, summary = fit_population_offset_poisson_glm(
        frame,
        "target_y",
        ["industrial_exposure_score"],
        "adult_population",
    )

    assert summary.model_type.startswith("Poisson GLM")
    assert summary.extra["offset_column"] == "adult_population"
    assert "offset(log(adult_population))" in summary.formula
    assert predictions["predicted_target_y"].gt(0).all()


def test_open_meteo_enrichment_adds_current_pollution_metrics(monkeypatch):
    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return [
                {"current": {"time": "2026-08-15T12:00", "pm2_5": 8.2, "nitrogen_dioxide": 4.1}},
                {"current": {"time": "2026-08-15T12:00", "pm2_5": 12.4, "nitrogen_dioxide": 7.3}},
            ]

    monkeypatch.setattr(
        "geo_pulse.ingestion.open_meteo_air_quality.httpx.get",
        lambda *args, **kwargs: Response(),
    )
    frame = pd.DataFrame({"latitude": [47.60, 47.61], "longitude": [-122.30, -122.31]})

    result = fetch_current_air_quality(frame)

    assert result["current_pm2_5"].tolist() == [8.2, 12.4]
    assert result["current_nitrogen_dioxide"].tolist() == [4.1, 7.3]
