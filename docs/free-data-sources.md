# Free Data Sources

## Kaggle properties

The default dataset handle is `ericpierce/austinhousingprices`, and the configured file is `austinHousingData.csv`. KaggleHub downloads the selected public file into `data/raw/kaggle/`. Geo-Pulse detects Kaggle's ZIP-wrapped file response, extracts only the requested member under a 500 MB safety limit, and normalizes its columns into the canonical property schema.

Other Kaggle datasets can be selected through the dashboard, CLI, or `ExternalAnalysisRequest`. If automatic column inference fails, set `data_sources.kaggle.column_mapping` as canonical-name to source-name mappings.

## OpenStreetMap

OSMnx queries Overpass for parks, schools, and transit inside the buffered property bounding box. Geo-Pulse refuses extents larger than the configured area limit so an accidentally nationwide Kaggle dataset cannot trigger an unreasonable Overpass query. OSM results are cached locally.

## Census demographics

Geo-Pulse calls the configured ACS 5-year API vintage for each unique ZIP Code Tabulation Area. It retrieves population, median household income, and median home value, then creates numerically scaled model features.

Current Census APIs require a free API key. Copy `.env.example` to `.env` and set `CENSUS_API_KEY`. The key remains server-side and is never included in reports or source manifests.

## Execution

Run `geo-pulse analyze-free` from the project directory, or start `geo-pulse serve` and use the **Free public data pipeline** section in the dashboard.

Each completed run writes a source manifest under `artifacts/run_metadata/` with the Kaggle source, resolved schema, ACS vintage, row counts, and OSM amenity coverage.
