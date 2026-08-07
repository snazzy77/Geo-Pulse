# Geo-Pulse

Geo-Pulse is an executable, local-first, schema-adaptive spatial analytics service. It can run its original real-estate enrichment workflow or inspect and standardize an arbitrary spatial table before fitting a geographic random-intercept mixed-effects model, testing residual spatial autocorrelation with permutation-based Moran's I, and publishing an interactive map plus an HTML report.

## Quick start

Requirements: Python 3.11 or later.

```text
python -m pip install -e ".[dev]"
python scripts/download_sample_data.py
geo-pulse analyze --question "How does park distance affect home price?" --properties data/samples/properties.csv --amenities data/samples/amenities.csv
```

Generated artifacts are written beneath `artifacts/`.

## Generic spatial workflow

Use `analyze-spatial` for non-housing data or housing files with unfamiliar column names:

~~~text
geo-pulse analyze-spatial --data data/health.csv --question "How is exposure associated with disease rate?"
~~~

Geo-Pulse first inspects the columns and suggests semantic roles for the target, coordinates or geometry, repeated geographic group, record identifier, and numeric fixed effects. Automatic inference is conservative: if a required role is ambiguous, provide an explicit mapping:

~~~text
geo-pulse analyze-spatial --data data/health.csv --target-column DiseaseRate --latitude-column Lat --longitude-column Lng --group-column CommunityArea --fixed-feature Pollution --fixed-feature Income --id-column CaseNumber --target-transform none
~~~

Projected X/Y sources are supported with `--source-crs`, and WKT/GeoJSON geometry can be selected with `--geometry-column`. The dashboard offers the same flow through **Generic spatial dataset → Inspect schema**. Schema aliases are configurable in `configs/default_schema.yaml`.

Every generic run writes a schema manifest containing the source-to-canonical mapping, inference confidence, canonical fixed effects, WGS84 normalization, and automatically selected local metric CRS.

## Free public data workflow

Create a `.env` file from `.env.example`, request a free Census API key, and add it as `CENSUS_API_KEY`. Add `KAGGLE_API_TOKEN` only when the chosen public Kaggle dataset requires authentication or user consent.

```text
geo-pulse analyze-free
```

The default live workflow downloads `ericpierce/austinhousingprices`, reads `austinHousingData.csv`, limits the analysis to 500 reproducibly sampled properties, retrieves parks, schools, and transit from OpenStreetMap through OSMnx, and joins 2024 ACS 5-year demographics by ZIP Code Tabulation Area.

## API

```text
geo-pulse serve
```

The command opens the Geo-Pulse dashboard at `http://127.0.0.1:8000`. From the dashboard you can run the included demonstration immediately or upload property and amenity files. API documentation remains available at `/docs`, and service health is available at `/health`.

## Input contracts

The housing workflow expects `property_id`, `price`, `latitude`, `longitude`, `neighborhood`, `square_feet`, `beds`, and `baths`. `year_built` is optional.

The generic workflow accepts CSV, JSON, JSONL, Parquet, GeoJSON, and GeoPackage sources. Its mapping requires a target, a repeated geographic group, at least one numeric fixed feature, and either latitude/longitude columns or a geometry column.

Amenity data must include `amenity_id`, `amenity_type`, `latitude`, and `longitude`. The default configuration recognizes `park`, `school`, and `transit`.

## Validation

```text
pytest
ruff check src tests scripts
ruff format --check src tests scripts
```

See `docs/pipeline.md` for the stage-by-stage design, controls, and file ownership.
