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

# Schema inspection

`POST /datasets/inspect` accepts a multipart `data` upload and returns a suggested generic mapping, confidence scores, warnings, and a five-row preview.

## Generic spatial analysis

`POST /analyses/spatial-upload` accepts:

- `question`: research question;
- `data`: CSV, JSON, JSONL, Parquet, GeoJSON, or GeoPackage file;
- `column_mapping`: optional JSON-encoded `DatasetColumnMapping`;
- `target_transform`: `auto`, `log`, or `none`.

When `column_mapping` is omitted, the agent inspection step attempts conservative automatic inference. Ambiguous datasets return HTTP 422 with guidance to provide an explicit mapping.
