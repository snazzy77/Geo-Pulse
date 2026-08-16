# API

Run the service with `geo-pulse dashboard` or `uvicorn geo_pulse.api.app:app`. Interactive OpenAPI documentation is served at `/docs`.

- `GET /health` reports service health.
- `POST /analyses` accepts the `AnalysisRequest` schema and executes the synchronous local pipeline.
- `POST /analyses/health-upload` runs environmental-health surveillance from outcome and hazard data.
- `POST /analyses/health-demo` runs the deterministic epidemiology demonstration.
- `POST /analyses/places-live` builds and analyzes a live CDC PLACES, Census, TIGERweb, and OSM tract matrix.
- `POST /analyses/external` executes the Kaggle, OSMnx, Census, and modeling pipeline.
- `GET /sources/status` reports whether source packages and environment credentials are configured without exposing secrets.
- `GET /sources/catalog` lists implemented free providers and controlled OSM feature classes.
- `POST /sources/osm/datasets` builds or retrieves a cached place-based OSM dataset.
- `GET /sources/osm/datasets/{dataset_id}/download` downloads the normalized CSV.
- `GET /datasets/osm/{dataset_id}/inspect` inspects a fetched OSM dataset in place.
- `POST /analyses/spatial-source` analyzes a fetched OSM dataset without re-uploading it.
- `GET /analyses/{run_id}` returns persisted run metadata.
- `GET /datasets` lists supported datasets beneath the configured data directory.
- `GET /models/{run_id}` returns the model summary.
- `GET /reports/{run_id}/report` serves the HTML report.
- `GET /reports/{run_id}/map` serves the interactive map.
- `GET /reports/{run_id}/matrix` downloads a live workflow's merged surveillance matrix.
- `GET /reports/{run_id}/predictions` downloads model predictions and residual alerts.

The MVP executes analyses synchronously. A production deployment should move long-running work to a durable job queue while retaining the same run identifiers and state model.

# Environmental-health surveillance

`POST /analyses/health-upload` accepts multipart fields: `question`, health-count `outcomes`, an optional hazard upload or cached OSM `hazard_dataset_id`, `buffer_m`, `alert_threshold`, repeated `demographic_controls`, optional `include_current_air_quality`, and optional JSON `column_mapping`. Demographic controls use the latest discoverable ACS 5-year release. It returns the standard response with surveillance map, epidemiologist report, Poisson model, predictions, diagnostics, schema manifest, policy memo, agent Markdown, and auditable agent-payload artifacts.

`POST /analyses/places-live` accepts JSON fields: `question`, `place`, five-digit `county_fips`, CDC `measure_id`, `buffer_m`, `alert_threshold`, `demographic_controls`, industrial `hazard_types`, and `max_hazards_per_type`. Defaults target Seattle/King County (`53033`) and current asthma (`CASTHMA`). The response adds a merged `surveillance_matrix` and complete `source_manifest` to the standard analysis artifacts.

# Schema inspection

`POST /datasets/inspect` accepts a multipart `data` upload and returns a suggested generic mapping, confidence scores, warnings, and a five-row preview.

## Generic spatial analysis

`POST /analyses/spatial-upload` accepts:

- `question`: research question;
- `data`: CSV, JSON, JSONL, Parquet, GeoJSON, or GeoPackage file;
- `column_mapping`: optional JSON-encoded `DatasetColumnMapping`;
- `target_transform`: `auto`, `log`, or `none`.
- `analysis_kind`: `auto`, `explore`, or `model`.

When `column_mapping` is omitted, the agent inspection step attempts conservative automatic inference. Coordinate-only datasets can run exploratory analysis without a target. Statistical modeling still requires an explicit or safely inferred target, group, and numeric fixed effects.
