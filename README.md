# Geo-Pulse

**Locate Exposure. Prevent Spikes.**

Geo-Pulse is a public-health surveillance dashboard that studies how nearby industrial
pollution may relate to community health vulnerabilities. It combines free public data,
spatial analysis, statistical modeling, and automated reporting in one local application.

## Mission

Geo-Pulse's mission is to help public-health teams identify communities that may need
closer investigation before health disparities become larger crises.

The application turns complex geographic and statistical data into clear maps, findings,
limitations, and practical surveillance recommendations. Geo-Pulse supports decision-making;
it does not prove that an environmental source caused an illness or replace review by an
epidemiologist.

## What Geo-Pulse does

Geo-Pulse can:

- Download community health estimates from **CDC PLACES**.
- Add demographic controls from the **U.S. Census Bureau**.
- Locate industrial sites using **OpenStreetMap**.
- Measure which communities are close to industrial hazards.
- Fit a population-adjusted Poisson health model.
- Detect unusual geographic health spikes and residual clustering.
- Convert model coefficients into understandable rate ratios.
- Generate an interactive map and a public-health report.
- Analyze your own health and environmental files.

## Quick start on Windows

### 1. Open the project

Open PowerShell and move into the Geo-Pulse folder:

```powershell
cd C:\Users\girid\Documents\Gokul_Projects\Gokul_Workspace\Geo-Pulse
```

### 2. Create and activate a virtual environment

You only need to create it once:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

If you already created the environment, only run the second command.

### 3. Install Geo-Pulse

```powershell
python -m pip install -e ".[dev]"
```

Geo-Pulse requires Python 3.11 or newer. Check your version with:

```powershell
python --version
```

### 4. Add your Census API key

Copy `.env.example` to a new file named `.env`, then add your key:

```text
CENSUS_API_KEY=your_key_here
```

Do not commit `.env` to GitHub. CDC PLACES and OpenStreetMap do not require API keys for
normal Geo-Pulse use.

### 5. Start the dashboard

```powershell
geo-pulse dashboard
```

Open <http://127.0.0.1:8000> if the browser does not open automatically. Stop the dashboard
with `Ctrl+C` in PowerShell.

## Run your first analysis

The dashboard starts in **Live Federal Streaming** mode.

1. Enter a research question.
2. Enter a study place and its five-digit county FIPS code.
3. Choose a health condition and environmental hazard type.
4. Optionally open **Advanced settings** to adjust the exposure buffer, spike threshold,
   and demographic controls.
5. Select **Run Geo-Pulse Surveillance**.
6. Review the findings, limitations, map, and full report.

The default example uses Seattle, Washington and King County FIPS `53033`.

To analyze private data instead, select **Custom Dataset Upload** and provide:

- A health outcome file containing community health measurements.
- A pollution or environmental file containing hazard locations.

Supported spatial formats include CSV, JSON, JSONL, Parquet, GeoJSON, and GeoPackage.

## Where results are saved

Each run creates files under the `artifacts/` directory, including:

- Interactive surveillance map
- Full HTML and Markdown reports
- Model summary and diagnostics
- Merged surveillance data when available
- Structured agent evidence for auditing

You can open these files from the dashboard after an analysis finishes.

## Useful command-line options

Run the same Seattle analysis without the dashboard:

```powershell
geo-pulse analyze-places --place "Seattle, Washington, USA" --county-fips 53033 --measure-id CASTHMA
```

Analyze your own health and hazard files:

```powershell
geo-pulse analyze-health --outcomes data\health_outcomes.csv --hazards data\industrial_sites.csv --question "How does industrial exposure relate to asthma spikes?"
```

Explore any dataset containing coordinates or point geometry:

```powershell
geo-pulse analyze-spatial --data data\locations.csv --question "Where are records clustered?" --analysis-kind explore
```

See every available command:

```powershell
geo-pulse --help
```

## Run the tests

Run the complete test suite:

```powershell
python -m pytest
```

Run only the dashboard tests:

```powershell
python -m pytest tests\integration\test_api.py -q
```

Check code quality:

```powershell
python -m ruff check src tests
```

## Data sources

| Source | Purpose | API key required? |
|---|---|---:|
| CDC PLACES | Modeled community health prevalence | No |
| U.S. Census ACS | Population and demographic controls | Yes |
| Census TIGERweb | Census tract boundaries | No |
| OpenStreetMap | Industrial and environmental locations | No |

CDC PLACES values are modeled small-area prevalence estimates, not individual patient
records. OpenStreetMap buffer counts represent proximity, not measured pollution exposure.
These limitations are included in generated reports.

## Troubleshooting

**`geo-pulse` is not recognized**

Activate the virtual environment and reinstall the project:

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
```

**The dashboard still shows an older design**

Restart the dashboard and press `Ctrl+F5` in the browser.

**Live data cannot be downloaded**

Confirm that you have an internet connection and that `CENSUS_API_KEY` is present in `.env`.
Public services may occasionally rate-limit requests; wait briefly and try again.

## More documentation

- [Pipeline and file responsibilities](docs/pipeline.md)
- [Modeling methodology](docs/modeling_methodology.md)
- [API guide](docs/api.md)
- [Data dictionary](docs/data_dictionary.md)

API documentation is also available at <http://127.0.0.1:8000/docs> while the dashboard is
running.
