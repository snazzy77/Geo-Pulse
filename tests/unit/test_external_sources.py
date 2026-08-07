import json
import zipfile

import geopandas as gpd
import httpx
import pandas as pd
from shapely.geometry import Point

from geo_pulse.ingestion.census_client import enrich_with_census
from geo_pulse.ingestion.kaggle_source import (
    _materialize_downloaded_file,
    normalize_kaggle_properties,
)
from geo_pulse.ingestion.osm_client import fetch_amenities_for_properties


def test_austin_kaggle_columns_normalize_to_pipeline_contract():
    frame = pd.DataFrame(
        {
            "zpid": range(30),
            "latestPrice": [500_000 + index for index in range(30)],
            "latitude": [30.25] * 30,
            "longitude": [-97.75] * 30,
            "zipcode": [78704] * 30,
            "livingArea": [1800] * 30,
            "numOfBedrooms": [3] * 30,
            "numOfBathrooms": [2] * 30,
            "yearBuilt": [2000] * 30,
        }
    )
    normalized, mapping = normalize_kaggle_properties(frame)
    assert len(normalized) == 30
    assert normalized.loc[0, "postal_code"] == "78704"
    assert normalized.loc[0, "price"] == 500_000
    assert mapping["square_feet"] == "livingArea"


def test_census_enrichment_uses_acs_values_and_scaled_features(tmp_path):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/acs/acs5")
        assert not request.url.path.endswith("/acs/acs5/")
        postal_code = request.url.params["for"].split(":", 1)[1]
        body = [
            ["NAME", "B01003_001E", "B19013_001E", "B25077_001E", "zip code tabulation area"],
            [f"ZCTA5 {postal_code}", "10000", "85000", "450000", postal_code],
        ]
        return httpx.Response(
            200, content=json.dumps(body), headers={"content-type": "application/json"}
        )

    properties = pd.DataFrame({"postal_code": ["78704", "78701"]})
    result = enrich_with_census(
        properties,
        year=2024,
        cache_dir=tmp_path,
        api_key="test-key",
        transport=httpx.MockTransport(handler),
    )
    assert result["census_population"].eq(10_000).all()
    assert result["census_income_10k"].eq(8.5).all()
    assert result["census_home_value_100k"].eq(4.5).all()


def test_census_errors_do_not_expose_api_key(tmp_path):
    secret = "do-not-leak-this-key"

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(404)

    try:
        enrich_with_census(
            pd.DataFrame({"postal_code": ["78704"]}),
            year=2024,
            cache_dir=tmp_path,
            api_key=secret,
            transport=httpx.MockTransport(handler),
        )
    except Exception as exc:  # noqa: BLE001 - assertion covers the public error surface
        message = str(exc)
    else:
        raise AssertionError("Expected Census failure")
    assert secret not in message
    assert "HTTP 404" in message


def test_kaggle_zip_wrapped_csv_is_materialized(tmp_path):
    archive_path = tmp_path / "properties.csv"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("properties.csv", "price,latitude\n500000,30.2\n")
    extracted = _materialize_downloaded_file(archive_path, "properties.csv")
    assert extracted != archive_path
    assert extracted.read_text(encoding="utf-8").startswith("price,latitude")


def test_osmnx_features_are_converted_to_amenity_records(monkeypatch, tmp_path):
    captured = {"calls": 0}

    def fake_features_from_bbox(bbox, tags):
        captured["calls"] += 1
        captured["bbox"] = bbox
        captured["tags"] = tags
        index = pd.MultiIndex.from_tuples(
            [("node", 123), ("node", 124), ("node", 125)], names=["element", "osmid"]
        )
        return gpd.GeoDataFrame(
            {
                "name": ["Test Park", "Test School", "Test Stop"],
                "leisure": ["park", None, None],
                "amenity": [None, "school", None],
                "public_transport": [None, None, "platform"],
            },
            geometry=[
                Point(-97.7431, 30.2672),
                Point(-97.7441, 30.2682),
                Point(-97.7421, 30.2662),
            ],
            index=index,
            crs="EPSG:4326",
        )

    monkeypatch.setattr("osmnx.features_from_bbox", fake_features_from_bbox)
    properties = pd.DataFrame({"latitude": [30.2672], "longitude": [-97.7431]})
    amenities = fetch_amenities_for_properties(
        properties,
        ["park", "school", "transit"],
        buffer_m=500,
        cache_dir=tmp_path,
        max_bbox_area_km2=25,
    )
    assert captured["calls"] == 1
    assert len(captured["bbox"]) == 4
    assert "leisure" in captured["tags"]
    assert set(amenities["amenity_type"]) == {"park", "school", "transit"}
    assert "osm-park-node-123" in set(amenities["amenity_id"])
