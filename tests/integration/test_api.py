from fastapi.testclient import TestClient

from geo_pulse.api.app import app
from geo_pulse.api.dependencies import get_settings
from geo_pulse.core.exceptions import DataValidationError
from geo_pulse.sample_data import generate_health_sample_data
from geo_pulse.schemas.reports import AnalysisResponse


def test_health_endpoint():
    response = TestClient(app).get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_free_source_catalog_lists_no_key_osm_features():
    response = TestClient(app).get("/sources/catalog")
    assert response.status_code == 200
    provider = response.json()["providers"][0]
    assert provider["key"] == "openstreetmap"
    assert provider["authentication"] == "No API key"
    assert any(item["key"] == "school" for item in provider["feature_types"])


def test_osm_provider_failure_returns_dashboard_safe_error(monkeypatch, test_settings):
    def fail_fetch(*args, **kwargs):
        raise DataValidationError("The public OSM service is temporarily busy")

    monkeypatch.setattr("geo_pulse.api.routes.sources.acquire_osm_place_dataset", fail_fetch)
    app.dependency_overrides[get_settings] = lambda: test_settings
    try:
        response = TestClient(app).post(
            "/sources/osm/datasets",
            json={"place": "Test City", "feature_type": "cafe", "max_rows": 25},
        )
        assert response.status_code == 422
        assert response.json()["detail"] == "The public OSM service is temporarily busy"
    finally:
        app.dependency_overrides.clear()


def test_dashboard_and_assets_are_served():
    client = TestClient(app)
    page = client.get("/")
    script = client.get("/static/app.js")
    stylesheet = client.get("/static/styles.css")
    assert page.status_code == 200
    assert "Surveillance configuration" in page.text
    assert "Locate Exposure." in page.text
    assert "Prevent Spikes." in page.text
    assert "An autonomous public health engine" in page.text
    assert "Live Federal Streaming" in page.text
    assert "Custom Dataset Upload" in page.text
    assert 'id="live-mode-fields"' in page.text
    assert 'id="custom-mode-fields"' in page.text
    assert 'id="run-surveillance-button"' in page.text
    assert 'id="theme-toggle"' in page.text
    assert "Light" in page.text
    assert "Dark" in page.text
    assert 'role="switch"' in page.text
    assert "Run Geo-Pulse Surveillance" in page.text
    assert "Fit population-offset Poisson model" in page.text
    assert "Analyze any spatial dataset" not in page.text
    assert "Find free spatial data" not in page.text
    assert 'id="fetch-osm-button"' not in page.text
    assert 'id="places-live-button"' not in page.text
    assert "Run health demo" not in page.text
    assert "ACS year" not in page.text
    assert "Median household income" in page.text
    assert "Anomalous spike threshold" in page.text
    assert "CDC PLACES" in page.text
    assert 'value="53033"' in page.text
    assert 'id="command-center"' in page.text
    assert "/static/app.js?v=" in page.text
    assert script.status_code == 200
    assert stylesheet.status_code == 200
    assert "--cyan:#00f6ff" in stylesheet.text
    assert "--blue:#168cff" in stylesheet.text
    assert "--amber:#ff8a1f" in stylesheet.text
    assert '[data-theme="villain"]' in stylesheet.text
    assert "--cyan:#ff6a00" in stylesheet.text
    assert "--green:" not in stylesheet.text
    assert "/analyses/health-upload" in script.text
    assert "/analyses/places-live" in script.text
    assert 'setMode("live")' in script.text
    assert 'localStorage.setItem(THEME_STORAGE_KEY' in script.text
    assert 'setTheme(document.documentElement.dataset.theme' in script.text
    assert 'mode === "custom"' in script.text
    assert 'id="matrix-link"' in page.text


def test_live_matrix_artifact_is_downloadable(tmp_path, test_settings):
    test_settings.artifact_dir = tmp_path / "artifacts"
    matrix_dir = test_settings.artifacts / "datasets"
    matrix_dir.mkdir(parents=True)
    (matrix_dir / "places-test-surveillance-matrix.csv").write_text(
        "tract_fips,estimated_cases\n53033000101,80\n", encoding="utf-8"
    )
    app.dependency_overrides[get_settings] = lambda: test_settings
    try:
        response = TestClient(app).get("/reports/places-test/matrix")
        assert response.status_code == 200
        assert "53033000101" in response.text
    finally:
        app.dependency_overrides.clear()


def test_live_places_endpoint_accepts_seattle_request(monkeypatch, test_settings):
    def fake_run(request, settings):
        assert request.county_fips == "53033"
        assert request.measure_id == "CASTHMA"
        return AnalysisResponse(
            run_id="places-test",
            status="completed",
            summary="Merged live federal sources.",
        )

    monkeypatch.setattr("geo_pulse.api.routes.analyses.run_places_surveillance", fake_run)
    app.dependency_overrides[get_settings] = lambda: test_settings
    try:
        response = TestClient(app).post(
            "/analyses/places-live",
            json={
                "question": "How is industrial proximity associated with asthma?",
                "place": "Seattle, Washington, USA",
                "county_fips": "53033",
                "measure_id": "CASTHMA",
            },
        )
        assert response.status_code == 200
        assert response.json()["run_id"] == "places-test"
    finally:
        app.dependency_overrides.clear()


def test_demo_analysis_is_accessible_from_dashboard(tmp_path, test_settings):
    test_settings.data_dir = tmp_path / "data"
    test_settings.artifact_dir = tmp_path / "artifacts"
    app.dependency_overrides[get_settings] = lambda: test_settings
    try:
        client = TestClient(app)
        response = client.post("/analyses/demo?question=Does%20park%20distance%20affect%20price%3F")
        assert response.status_code == 200
        payload = response.json()
        run_id = payload["run_id"]
        assert client.get(f"/reports/{run_id}/map").status_code == 200
        assert client.get(f"/reports/{run_id}/report").status_code == 200
        assert client.get(f"/models/{run_id}").status_code == 200
    finally:
        app.dependency_overrides.clear()


def test_uploaded_files_run_an_analysis(tmp_path, test_settings, sample_paths):
    test_settings.data_dir = tmp_path / "data"
    test_settings.artifact_dir = tmp_path / "artifacts"
    app.dependency_overrides[get_settings] = lambda: test_settings
    try:
        client = TestClient(app)
        with sample_paths[0].open("rb") as properties, sample_paths[1].open("rb") as amenities:
            response = client.post(
                "/analyses/upload",
                data={
                    "question": "How does park distance affect price?",
                    "target": "price",
                    "group_column": "neighborhood",
                },
                files={
                    "properties": ("properties.csv", properties, "text/csv"),
                    "amenities": ("amenities.csv", amenities, "text/csv"),
                },
            )
        assert response.status_code == 200
        assert response.json()["status"] in {"completed", "completed-with-limitations"}
    finally:
        app.dependency_overrides.clear()


def test_external_analysis_reports_missing_census_key(monkeypatch, test_settings):
    monkeypatch.delenv("CENSUS_API_KEY", raising=False)
    app.dependency_overrides[get_settings] = lambda: test_settings
    try:
        response = TestClient(app).post(
            "/analyses/external",
            json={
                "question": "How do public spatial features affect price?",
                "kaggle_dataset": "ericpierce/austinhousingprices",
                "kaggle_filename": "austinHousingData.csv",
                "max_rows": 100,
            },
        )
        assert response.status_code == 422
        assert "CENSUS_API_KEY" in response.json()["detail"]
    finally:
        app.dependency_overrides.clear()


def test_schema_inspection_endpoint_suggests_mapping(tmp_path, test_settings):
    test_settings.data_dir = tmp_path / "data"
    app.dependency_overrides[get_settings] = lambda: test_settings
    frame = (
        "record_id,disease_rate,latitude,longitude,district,exposure\n"
        "a,2.1,41.8,-87.7,north,4.0\n"
        "b,2.4,41.9,-87.6,south,5.0\n"
    )
    try:
        response = TestClient(app).post(
            "/datasets/inspect",
            files={"data": ("health.csv", frame.encode(), "text/csv")},
        )
        assert response.status_code == 200
        mapping = response.json()["suggested_mapping"]
        assert mapping["target_variable"] == "disease_rate"
        assert mapping["group_col"] == "district"
        assert mapping["fixed_features"] == ["exposure"]
    finally:
        app.dependency_overrides.clear()


def test_fetched_osm_dataset_runs_general_spatial_analysis(tmp_path, test_settings):
    test_settings.data_dir = tmp_path / "data"
    test_settings.artifact_dir = tmp_path / "artifacts"
    dataset_id = "abc123def456"
    source_dir = test_settings.data_dir / "external" / "osm"
    source_dir.mkdir(parents=True)
    (source_dir / f"{dataset_id}.csv").write_text(
        "record_id,feature_type,name,latitude,longitude,source\n"
        "osm-node-1,cafe,Alpha,47.610,-122.340,OpenStreetMap\n"
        "osm-node-2,cafe,Beta,47.611,-122.341,OpenStreetMap\n"
        "osm-node-3,cafe,Gamma,47.620,-122.330,OpenStreetMap\n"
        "osm-node-4,cafe,Delta,47.621,-122.331,OpenStreetMap\n",
        encoding="utf-8",
    )
    app.dependency_overrides[get_settings] = lambda: test_settings
    try:
        client = TestClient(app)
        inspection = client.get(f"/datasets/osm/{dataset_id}/inspect")
        response = client.post(
            "/analyses/spatial-source",
            json={
                "dataset_id": dataset_id,
                "question": "Where are the cafés clustered?",
                "analysis_kind": "auto",
            },
        )
        assert inspection.status_code == 200
        assert inspection.json()["row_count"] == 4
        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] == "completed"
        assert "spatial_pattern" not in payload["artifacts"]
        assert "model" not in payload["artifacts"]
        assert client.get(f"/reports/{payload['run_id']}/map").status_code == 200
        assert client.get(f"/reports/{payload['run_id']}/report").status_code == 200
    finally:
        app.dependency_overrides.clear()


def test_health_upload_uses_cached_osm_hazards_without_reupload(tmp_path, test_settings):
    outcomes, generated_hazards = generate_health_sample_data(tmp_path / "generated", seed=42)
    test_settings.data_dir = tmp_path / "data"
    test_settings.artifact_dir = tmp_path / "artifacts"
    dataset_id = "feed1234abcd"
    osm_dir = test_settings.data_dir / "external" / "osm"
    osm_dir.mkdir(parents=True)
    (osm_dir / f"{dataset_id}.csv").write_bytes(generated_hazards.read_bytes())
    app.dependency_overrides[get_settings] = lambda: test_settings
    try:
        with outcomes.open("rb") as outcome_stream:
            response = TestClient(app).post(
                "/analyses/health-upload",
                data={
                    "question": "Do industrial hazards predict asthma spikes?",
                    "hazard_dataset_id": dataset_id,
                    "buffer_m": "2000",
                },
                files={"outcomes": ("health.csv", outcome_stream, "text/csv")},
            )
        assert response.status_code == 200
        payload = response.json()
        assert "Poisson GLMM" in payload["summary"]
        assert "policy_memo" in payload["artifacts"]
    finally:
        app.dependency_overrides.clear()
