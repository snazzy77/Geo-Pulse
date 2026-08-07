from fastapi.testclient import TestClient

from geo_pulse.api.app import app
from geo_pulse.api.dependencies import get_settings


def test_health_endpoint():
    response = TestClient(app).get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_dashboard_and_assets_are_served():
    client = TestClient(app)
    page = client.get("/")
    script = client.get("/static/app.js")
    assert page.status_code == 200
    assert "Run sample analysis" in page.text
    assert script.status_code == 200
    assert "/analyses/upload" in script.text


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
