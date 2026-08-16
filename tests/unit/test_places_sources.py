import json

import httpx

from geo_pulse.ingestion.cdc_places_client import fetch_cdc_places_measure
from geo_pulse.ingestion.census_client import (
    fetch_county_tract_boundaries,
    fetch_county_tract_demographics,
)


def test_cdc_places_uses_adult_denominator_for_estimated_cases(tmp_path):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["$where"].startswith("countyfips = '53033'")
        return httpx.Response(
            200,
            json=[
                {
                    "year": "2023",
                    "stateabbr": "WA",
                    "countyname": "King",
                    "countyfips": "53033",
                    "locationname": "53033000101",
                    "measure": "Current asthma among adults",
                    "measureid": "CASTHMA",
                    "data_value": "8.0",
                    "data_value_unit": "%",
                    "data_value_type": "Crude prevalence",
                    "totalpopulation": "2000",
                    "totalpop18plus": "1000",
                    "geolocation": {"type": "Point", "coordinates": [-122.3, 47.6]},
                }
            ],
        )

    frame, metadata = fetch_cdc_places_measure(
        "53033",
        cache_dir=tmp_path,
        transport=httpx.MockTransport(handler),
    )

    assert frame.loc[0, "estimated_cases"] == 80
    assert frame.loc[0, "adult_population"] == 1000
    assert frame.loc[0, "tract_fips"] == "53033000101"
    assert metadata["dataset_id"] == "cwsq-ngmh"


def test_census_tract_demographics_and_tiger_boundaries_share_fips(tmp_path):
    controls = ["median_household_income", "percent_below_poverty"]

    def acs_handler(request: httpx.Request) -> httpx.Response:
        requested = request.url.params["get"].split(",")
        values = {
            "NAME": "Census Tract 1.01, King County, Washington",
            "B19013_001E": "90000",
            "B17001_001E": "1000",
            "B17001_002E": "125",
            "B01001_001E": "1200",
            **{f"B01001_{index:03d}E": "10" for index in range(20, 26)},
            **{f"B01001_{index:03d}E": "10" for index in range(44, 50)},
        }
        body = [
            [*requested, "state", "county", "tract"],
            [*(values[item] for item in requested), "53", "033", "000101"],
        ]
        return httpx.Response(200, content=json.dumps(body))

    demographics, year = fetch_county_tract_demographics(
        "53033",
        controls,
        tmp_path,
        api_key="test-key",
        year=2025,
        transport=httpx.MockTransport(acs_handler),
    )

    def tiger_handler(request: httpx.Request) -> httpx.Response:
        assert "STATE='53'" in request.url.params["where"]
        return httpx.Response(
            200,
            json={
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "properties": {
                            "GEOID": "53033000101",
                            "NAME": "Census Tract 1.01",
                            "CENTLAT": "+47.6000000",
                            "CENTLON": "-122.3000000",
                        },
                        "geometry": {
                            "type": "Polygon",
                            "coordinates": [
                                [
                                    [-122.31, 47.59],
                                    [-122.29, 47.59],
                                    [-122.29, 47.61],
                                    [-122.31, 47.61],
                                    [-122.31, 47.59],
                                ]
                            ],
                        },
                    }
                ],
            },
        )

    boundaries = fetch_county_tract_boundaries(
        "53033", tmp_path, transport=httpx.MockTransport(tiger_handler)
    )

    assert year == 2025
    assert demographics.loc[0, "tract_fips"] == boundaries.loc[0, "tract_fips"]
    assert demographics.loc[0, "census_median_household_income_10k"] == 9.0
    assert demographics.loc[0, "census_percent_below_poverty"] == 12.5
    assert boundaries.geometry.iloc[0].geom_type == "Polygon"
