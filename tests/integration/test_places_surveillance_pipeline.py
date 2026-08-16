import geopandas as gpd
import pandas as pd
from shapely.geometry import box

from geo_pulse.pipelines.places_surveillance_pipeline import build_places_surveillance_matrix
from geo_pulse.schemas.requests import PlacesSurveillanceRequest


def test_live_sources_merge_on_tract_fips_and_build_exposure(monkeypatch, tmp_path, test_settings):
    tract_ids = [f"53033{index:06d}" for index in range(1, 31)]
    latitudes = [47.50 + index * 0.004 for index in range(30)]
    longitudes = [-122.40 + index * 0.004 for index in range(30)]
    boundaries = gpd.GeoDataFrame(
        {
            "tract_fips": tract_ids,
            "tract_name": [f"Tract {index}" for index in range(30)],
            "latitude": latitudes,
            "longitude": longitudes,
        },
        geometry=[
            box(lon - 0.002, lat - 0.002, lon + 0.002, lat + 0.002)
            for lat, lon in zip(latitudes, longitudes, strict=True)
        ],
        crs="EPSG:4326",
    )
    demographics = pd.DataFrame(
        {
            "tract_fips": tract_ids,
            "census_median_household_income_10k": [7 + index / 10 for index in range(30)],
            "census_percent_below_poverty": [8 + index / 5 for index in range(30)],
            "census_percent_age_65_plus": [10 + index / 10 for index in range(30)],
        }
    )
    cdc = pd.DataFrame(
        {
            "tract_fips": tract_ids,
            "record_id": tract_ids,
            "county_fips": "53033",
            "measure_id": "CASTHMA",
            "measure": "Current asthma among adults",
            "data_year": "2023",
            "prevalence_pct": [7 + index / 10 for index in range(30)],
            "total_population": 1500,
            "adult_population": [1000 + index * 10 for index in range(30)],
            "estimated_cases": [70 + index for index in range(30)],
            "latitude": latitudes,
            "longitude": longitudes,
        }
    )

    monkeypatch.setattr(
        "geo_pulse.pipelines.places_surveillance_pipeline.fetch_cdc_places_measure",
        lambda *args, **kwargs: (cdc, {"dataset_id": "cwsq-ngmh"}),
    )
    monkeypatch.setattr(
        "geo_pulse.pipelines.places_surveillance_pipeline.fetch_county_tract_demographics",
        lambda *args, **kwargs: (demographics, 2025),
    )
    monkeypatch.setattr(
        "geo_pulse.pipelines.places_surveillance_pipeline.fetch_county_tract_boundaries",
        lambda *args, **kwargs: boundaries,
    )

    def fake_osm(place, hazard_type, *args, **kwargs):
        frame = pd.DataFrame(
            {
                "record_id": [f"{hazard_type}-1"],
                "latitude": [47.55],
                "longitude": [-122.35],
            }
        )
        return frame, {"provider": "OpenStreetMap", "feature_type": hazard_type}

    monkeypatch.setattr(
        "geo_pulse.pipelines.places_surveillance_pipeline.fetch_osm_place_dataset", fake_osm
    )
    monkeypatch.setenv("CENSUS_API_KEY", "test-key")
    test_settings.cache_dir = tmp_path / "cache"
    request = PlacesSurveillanceRequest(
        question="How is industrial proximity associated with asthma?"
    )

    matrix, fixed_effects, metadata = build_places_surveillance_matrix(request, test_settings)

    assert len(matrix) == 30
    assert matrix["tract_fips"].is_unique
    assert "industrial_exposure_score" in matrix
    assert "census_median_household_income_10k" in fixed_effects
    assert metadata["census_dataset"] == "2025 ACS 5-year"
    assert metadata["joined_tract_count"] == 30
