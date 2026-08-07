# API

Run the service with `geo-pulse serve` or `uvicorn geo_pulse.api.app:app`. Interactive OpenAPI documentation is served at `/docs`.

- `GET /health` reports service health.
- `POST /analyses` accepts the `AnalysisRequest` schema and executes the synchronous local pipeline.
- `POST /analyses/external` executes the Kaggle, OSMnx, Census, and modeling pipeline.
- `GET /sources/status` reports whether source packages and environment credentials are configured without exposing secrets.
- `GET /analyses/{run_id}` returns persisted run metadata.
- `GET /datasets` lists supported datasets beneath the configured data directory.
- `GET /models/{run_id}` returns the model summary.
- `GET /reports/{run_id}/report` serves the HTML report.
- `GET /reports/{run_id}/map` serves the interactive map.

The MVP executes analyses synchronously. A production deployment should move long-running work to a durable job queue while retaining the same run identifiers and state model.
