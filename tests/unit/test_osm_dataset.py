import geopandas as gpd
import pandas as pd
from shapely.geometry import Polygon

from geo_pulse.ingestion.osm_dataset import (
    fetch_osm_place_dataset,
    osm_feature_catalog,
)
from geo_pulse.pipelines.source_acquisition_pipeline import acquire_osm_place_dataset
from geo_pulse.schemas.sources import OSMPlaceDatasetRequest


def test_osm_catalog_exposes_controlled_feature_types():
    catalog = osm_feature_catalog()
    keys = {feature.key for feature in catalog}
    assert {
        "industrial_zone",
        "factory",
        "refinery",
        "power_plant",
        "school",
        "hospital",
        "park",
        "transit",
        "apartments",
    } <= keys
    assert all(feature.description for feature in catalog)


def test_osm_place_fetch_normalizes_and_limits_features(monkeypatch, tmp_path):
    boundary = gpd.GeoDataFrame(
        {"display_name": ["Test City"]},
        geometry=[
            Polygon(
                [
                    (-122.36, 47.60),
                    (-122.34, 47.60),
                    (-122.34, 47.62),
                    (-122.36, 47.62),
                ]
            )
        ],
        crs="EPSG:4326",
    )
    elements = [
        {
            "type": "node",
            "id": 1,
            "lat": 47.61,
            "lon": -122.35,
            "tags": {"name": "Alpha School", "operator": "District"},
        },
        {
            "type": "way",
            "id": 2,
            "center": {"lat": 47.611, "lon": -122.351},
            "tags": {"name": "Beta School"},
        },
        {"type": "node", "id": 3, "lat": 47.612, "lon": -122.352, "tags": {}},
    ]
    captured = {}

    def fake_geocode(place):
        captured["place"] = place
        return boundary

    def fake_overpass(endpoint, query, timeout_s, user_agent):
        captured["endpoint"] = endpoint
        captured["query"] = query
        return elements

    monkeypatch.setattr("osmnx.geocode_to_gdf", fake_geocode)
    monkeypatch.setattr(
        "geo_pulse.ingestion.osm_dataset._request_overpass", fake_overpass
    )

    frame, metadata = fetch_osm_place_dataset(
        "Test City",
        "school",
        max_rows=2,
        cache_dir=tmp_path,
    )

    assert captured["place"] == "Test City"
    assert '["amenity"="school"]' in captured["query"]
    assert '["amenity"="college"]' in captured["query"]
    assert len(frame) == 2
    assert frame["latitude"].between(47.60, 47.62).all()
    assert {"record_id", "latitude", "longitude", "feature_area_m2"} <= set(frame.columns)
    assert metadata["total_features_found"] == 3
    assert metadata["truncated"] is True


def test_osm_acquisition_pipeline_reuses_export_cache(monkeypatch, tmp_path, test_settings):
    test_settings.data_dir = tmp_path / "data"
    calls = {"count": 0}

    def fake_fetch(*args, **kwargs):
        calls["count"] += 1
        frame = pd.DataFrame(
            {
                "record_id": ["osm-node-1"],
                "feature_type": ["library"],
                "latitude": [47.61],
                "longitude": [-122.35],
            }
        )
        return frame, {
            "provider": "OpenStreetMap",
            "place": "Test City",
            "feature_type": "library",
            "total_features_found": 1,
            "returned_rows": 1,
            "truncated": False,
            "attribution": "© OpenStreetMap contributors",
            "license_url": "https://www.openstreetmap.org/copyright",
        }

    monkeypatch.setattr(
        "geo_pulse.pipelines.source_acquisition_pipeline.fetch_osm_place_dataset",
        fake_fetch,
    )
    request = OSMPlaceDatasetRequest(place="Test City", feature_type="library", max_rows=10)

    first = acquire_osm_place_dataset(request, test_settings)
    second = acquire_osm_place_dataset(request, test_settings)

    assert calls["count"] == 1
    assert first.cached is False
    assert second.cached is True
    assert __import__("pathlib").Path(first.local_path).is_file()
