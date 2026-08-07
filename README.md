# Geo-Pulse

Geo-Pulse is an executable, local-first real-estate spatial analytics service. It enriches property records with amenity-distance features, estimates a neighborhood random-intercept mixed-effects model, tests residual spatial autocorrelation with permutation-based Moran's I, applies one bounded spatial correction when configured, and publishes an interactive map plus an HTML report.

## Quick start

Requirements: Python 3.11 or later.

```text
python -m pip install -e ".[dev]"
python scripts/download_sample_data.py
geo-pulse analyze --question "How does park distance affect home price?" --properties data/samples/properties.csv --amenities data/samples/amenities.csv
```

Generated artifacts are written beneath `artifacts/`.

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

Property data must include `property_id`, `price`, `latitude`, `longitude`, `neighborhood`, `square_feet`, `beds`, and `baths`. `year_built` is optional.

Amenity data must include `amenity_id`, `amenity_type`, `latitude`, and `longitude`. The default configuration recognizes `park`, `school`, and `transit`.

## Validation

```text
pytest
ruff check src tests scripts
ruff format --check src tests scripts
```

See `docs/pipeline.md` for the stage-by-stage design, controls, and file ownership.
