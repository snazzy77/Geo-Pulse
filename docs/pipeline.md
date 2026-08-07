# Geo-Pulse Analysis Pipeline

## Purpose

This document is the operating blueprint for Geo-Pulse. It defines how a natural-language real-estate question becomes a reproducible spatial analysis, a validated statistical model, an interactive map, and an executive report.

Geo-Pulse follows one central rule: the AI agent may interpret, plan, coordinate, and explain, but all data transformations, geographic calculations, statistical estimates, diagnostic tests, and metrics must be produced by deterministic modules.

## End-to-end flow

```text
User question
    ↓
Request validation
    ↓
Agent analysis plan
    ↓
Property, boundary, and amenity ingestion
    ↓
Data validation and geographic standardization
    ↓
GIS enrichment and feature engineering
    ↓
Model-ready dataset construction
    ↓
Mixed-effects model training and prediction
    ↓
Residual and spatial diagnostics
    ↓
Diagnostic decision
    ├── PASS ────────────────→ Publishing
    ├── REVISE → Correction → Retraining → Diagnostics
    └── STOP ────────────────→ Limited-results report
                                      ↓
                         Map, report, and final response
```

## Pipeline-wide records

Every analysis receives a unique run identifier. `core/run_context.py` owns the in-memory run context, while `storage/run_repository.py` persists its state.

The run record must identify:

- The original user request and accepted analysis plan
- Configuration versions and model specification
- Source datasets and acquisition timestamps
- Geographic area and coordinate systems
- Stage start times, completion times, and outcomes
- Validation warnings and failures
- Model versions, correction attempts, and diagnostic decisions
- Paths or identifiers for every generated artifact
- Final completion status and known limitations

Valid run states should include received, planning, ingesting, engineering, modeling, diagnosing, correcting, publishing, completed, completed-with-limitations, and failed.

## Stage 1: Receive and validate the request

### Purpose

Convert an incoming API or command-line request into a validated request object without yet making analytical claims.

### Responsible files

- `src/geo_pulse/api/routes/analyses.py` accepts API analysis requests and exposes run status.
- `src/geo_pulse/main.py` serves as the future command-line entry point.
- `src/geo_pulse/schemas/requests.py` defines required and optional request fields.
- `src/geo_pulse/agent/guardrails.py` checks scope, privacy, supported geographies, and unsupported claims.
- `src/geo_pulse/core/run_context.py` creates the analysis run identity and initial state.
- `src/geo_pulse/storage/run_repository.py` persists the accepted request.

### Expected inputs

- Natural-language question
- Geographic area
- Property dataset or approved data source
- Optional date range and property filters
- Optional target variable, amenities, grouping level, and output preferences

### Validation gate

The request proceeds only if its geography, target, data source, and intended analysis are supported. Missing optional details may be resolved by documented defaults. Material ambiguity must be returned to the user rather than silently guessed.

### Output

A validated request associated with a run identifier.

## Stage 2: Build the analysis plan

### Purpose

Translate the validated request into an explicit, inspectable sequence of analytical steps.

### Responsible files

- `src/geo_pulse/agent/planner.py` creates the structured plan.
- `src/geo_pulse/agent/orchestrator.py` coordinates the plan-execute-observe cycle.
- `src/geo_pulse/agent/state.py` records planned and completed actions.
- `src/geo_pulse/agent/prompts.py` contains versioned planning instructions.
- `src/geo_pulse/agent/tool_registry.py` limits the plan to registered capabilities.
- `src/geo_pulse/schemas/features.py` and `schemas/models.py` constrain proposed features and models.

### The plan must state

- Analysis target, such as sale price or log sale price
- Geographic study area and grouping level
- Population and filters
- Required property attributes
- Amenities and spatial features to acquire
- Straight-line or network distance requirements
- Candidate fixed effects
- Candidate random effects
- Spatial diagnostic method and thresholds
- Permitted correction strategy
- Required map, chart, and report outputs

### Validation gate

Every proposed action must map to an approved tool and configuration. The agent cannot invent unavailable data, features, or analytical capabilities.

### Output

A versioned analysis plan stored with the run metadata.

## Stage 3: Ingest source data

### Purpose

Acquire property records, geographic boundaries, coordinates, amenities, and street networks while preserving source lineage.

### Responsible files

- `src/geo_pulse/pipelines/ingestion_pipeline.py` coordinates the stage.
- `src/geo_pulse/ingestion/property_provider.py` defines the shared provider contract.
- `src/geo_pulse/ingestion/property_loader.py` reads property records.
- `src/geo_pulse/ingestion/geocoder.py` resolves missing property coordinates.
- `src/geo_pulse/ingestion/osm_client.py` retrieves OpenStreetMap amenities and networks.
- `src/geo_pulse/ingestion/boundary_loader.py` loads neighborhood, ZIP, tract, or other boundaries.
- `src/geo_pulse/ingestion/validators.py` performs initial source validation.
- `src/geo_pulse/storage/cache.py` prevents unnecessary repeated external requests.
- `src/geo_pulse/storage/dataset_store.py` versions source and interim datasets.

### Data-zone behavior

- `data/raw/` contains immutable copies of acquired source data.
- `data/external/` contains independently managed reference datasets.
- `data/interim/` contains standardized records produced during ingestion.

Raw files must never be modified in place.

### Validation gate

The ingestion stage checks required fields, source accessibility, schema compatibility, duplicate identifiers, price plausibility, coordinate validity, boundary coverage, geocoding quality, sample size, and acquisition completeness.

### Output

Versioned property, boundary, amenity, and network datasets with provenance metadata.

## Stage 4: Standardize geography

### Purpose

Create valid geometries, use appropriate coordinate systems, and connect each property to geographic groups.

### Responsible files

- `src/geo_pulse/gis/geometries.py` creates and repairs supported geometries.
- `src/geo_pulse/gis/crs.py` selects and applies geographic and projected coordinate systems.
- `src/geo_pulse/gis/neighborhood_assigner.py` performs property-to-boundary assignments.
- `src/geo_pulse/ingestion/validators.py` checks post-transformation geographic validity.

### Required behavior

Latitude and longitude may be retained for display, but metric distance calculations must use an appropriate projected coordinate reference system. The run metadata must record both source and analytical coordinate systems.

### Validation gate

Properties must fall inside or within an approved tolerance of the study area. Invalid, empty, or mismatched geometries must be repaired under a documented rule or excluded with a recorded reason.

### Output

Validated property, amenity, and boundary geometries in the coordinate systems needed by later stages.

## Stage 5: Engineer spatial and housing features

### Purpose

Transform raw attributes and geographic context into documented, reproducible model features.

### Responsible files

- `src/geo_pulse/pipelines/feature_pipeline.py` coordinates the stage.
- `src/geo_pulse/gis/amenity_extractor.py` normalizes requested amenity types.
- `src/geo_pulse/gis/distance_calculator.py` calculates projected straight-line distances.
- `src/geo_pulse/gis/network_calculator.py` calculates walking or driving network distances.
- `src/geo_pulse/gis/density_calculator.py` calculates counts and densities within radii.
- `src/geo_pulse/features/housing_features.py` derives structural property features.
- `src/geo_pulse/features/spatial_features.py` derives geographic-context features.
- `src/geo_pulse/features/transformations.py` applies configured transformations.
- `src/geo_pulse/features/builder.py` combines and validates all engineered features.
- `src/geo_pulse/features/feature_catalog.py` records definitions, units, and lineage.

### Candidate outputs

- Distance to nearest park, school, transit stop, or highway
- Amenity counts or densities within configured distances
- Walking or driving accessibility measures
- Neighborhood, ZIP, or tract assignment
- Living-area, age, bed, bath, lot, and property-type features
- Approved logarithmic, scaled, clipped, interaction, or nonlinear features

### Validation gate

Features must have known units, valid ranges, documented missing-value behavior, adequate variation, and a direct lineage to source records. Features with leakage from the target or future information must be rejected.

### Output

A versioned feature dataset in `data/processed/` and a matching feature catalog.

## Stage 6: Build the model dataset

### Purpose

Create the exact reproducible dataset and specification used for estimation and evaluation.

### Responsible files

- `src/geo_pulse/modeling/dataset_builder.py` selects eligible observations and features.
- `src/geo_pulse/modeling/formula_builder.py` constructs approved model specifications.
- `src/geo_pulse/schemas/models.py` defines the model input contract.
- `src/geo_pulse/configs/models.yaml` will contain thresholds and approved defaults.

### Required decisions

- Target definition and transformation
- Included fixed effects
- Random-intercept or random-slope grouping
- Handling of missing data and outliers
- Training and evaluation strategy
- Minimum group sizes
- Reference categories
- Reproducibility seed where applicable

### Validation gate

The stage must reject specifications with insufficient observations, unusable group structure, constant predictors, unsupported variables, or direct target leakage.

### Output

An immutable model dataset, formula, feature list, grouping definition, and split metadata.

## Stage 7: Train, evaluate, and predict

### Purpose

Estimate global property-price relationships and neighborhood-level variation, then generate predictions and residuals.

### Responsible files

- `src/geo_pulse/pipelines/modeling_pipeline.py` coordinates training and prediction.
- `src/geo_pulse/modeling/mixed_effects.py` fits the primary hierarchical model.
- `src/geo_pulse/modeling/spatial_model.py` contains approved spatial alternatives.
- `src/geo_pulse/modeling/trainer.py` coordinates fitting and convergence handling.
- `src/geo_pulse/modeling/predictor.py` creates predictions, intervals, and residuals.
- `src/geo_pulse/modeling/evaluator.py` computes model-quality measures.
- `src/geo_pulse/modeling/model_registry.py` versions accepted model artifacts.
- `src/geo_pulse/storage/artifact_store.py` persists artifacts.

### Required outputs

- Fixed-effect estimates and uncertainty
- Random-effect estimates by geographic group
- Model convergence status
- Predicted values and prediction uncertainty when supported
- Residuals
- In-sample and held-out metrics as configured
- Formula, feature, dataset, and software-version lineage

### Validation gate

The model cannot proceed as valid if it fails to converge, produces invalid estimates, violates configured minimum quality thresholds, or lacks sufficient data for the requested grouping.

### Output

A versioned candidate model, evaluation record, prediction table, and residual table.

## Stage 8: Run statistical and spatial diagnostics

### Purpose

Determine whether the candidate model is adequate and whether its errors retain unexplained geographic structure.

### Responsible files

- `src/geo_pulse/diagnostics/residuals.py` validates and spatially attaches residuals.
- `src/geo_pulse/gis/spatial_weights.py` builds the required neighbor structure.
- `src/geo_pulse/diagnostics/morans_i.py` calculates global Moran's I and its significance.
- `src/geo_pulse/diagnostics/assumptions.py` checks non-spatial model assumptions.
- `src/geo_pulse/diagnostics/diagnostic_runner.py` returns the overall decision.
- `src/geo_pulse/tools/diagnostic_tool.py` exposes the stage to the agent.

### Diagnostic decision

- **PASS:** Required checks meet configured thresholds and residual spatial clustering is not statistically material.
- **REVISE:** A recognized, correctable problem exists and at least one approved correction remains.
- **STOP:** The model cannot be responsibly corrected with the available data or the retry limit has been reached.

Moran's I is evidence about residual spatial autocorrelation; it is not by itself proof of causation or overall model validity.

### Output

A diagnostic bundle in `artifacts/diagnostics/` containing test values, significance values, assumptions, warnings, spatial-weight metadata, and the decision rationale.

## Stage 9: Apply bounded corrections

### Purpose

Revise a failed candidate model using only predefined, auditable actions.

### Responsible files

- `src/geo_pulse/pipelines/correction_pipeline.py` coordinates correction attempts.
- `src/geo_pulse/diagnostics/correction_policy.py` maps failures to permitted actions.
- `src/geo_pulse/modeling/formula_builder.py` creates the revised specification.
- `src/geo_pulse/agent/orchestrator.py` records the tool result and initiates retraining.

### Examples of permitted corrections

- Add an already available and approved spatial feature
- Apply an approved nonlinear distance transformation
- Change to a configured geographic grouping with adequate sample support
- Use an approved spatial model specification
- Remove or flag invalid observations under a documented data-quality rule
- Stop and report insufficient data

### Prohibited behavior

- Unlimited retries
- Searching specifications solely until a preferred significance result appears
- Adding unavailable or invented variables
- Silently changing the target population
- Hiding failed specifications or diagnostics
- Claiming that correction proves causality

### Retry control

The maximum number of correction attempts belongs in `configs/models.yaml`. Every attempt must retain its specification, reason, outcome, metrics, and diagnostic bundle. A repeated failure ends with completed-with-limitations or failed status rather than another automatic loop.

### Output

Either a revised candidate returned to Stage 7 or a documented stop decision sent to publishing.

## Stage 10: Build maps and visual evidence

### Purpose

Make the accepted results geographically inspectable without overstating the model's conclusions.

### Responsible files

- `src/geo_pulse/visualization/map_builder.py` assembles and exports the map.
- `src/geo_pulse/visualization/layers.py` defines visible data layers.
- `src/geo_pulse/visualization/styles.py` defines colors, legends, and accessibility rules.
- `src/geo_pulse/visualization/tooltips.py` defines property and area details.
- `src/geo_pulse/visualization/charts.py` creates supporting statistical graphics.
- `src/geo_pulse/tools/map_tool.py` exposes map generation to the agent.

### Candidate map layers

- Property locations
- Observed and predicted prices
- Residuals
- Amenities
- Neighborhood or ZIP boundaries
- Neighborhood random effects
- Distance or accessibility measures

Map legends must distinguish observations, predictions, model effects, and heuristic opportunity labels. Sensitive record-level information must be suppressed or aggregated according to policy.

### Output

Interactive maps stored in `artifacts/maps/` and charts stored with the diagnostic or report artifacts.

## Stage 11: Generate the report

### Purpose

Present results to both nontechnical and technical audiences while preserving uncertainty, provenance, and limitations.

### Responsible files

- `src/geo_pulse/pipelines/publishing_pipeline.py` coordinates all publication work.
- `src/geo_pulse/reporting/insight_generator.py` creates evidence-bounded findings.
- `src/geo_pulse/reporting/executive_summary.py` creates the stakeholder summary.
- `src/geo_pulse/reporting/statistical_summary.py` creates the technical record.
- `src/geo_pulse/reporting/report_builder.py` assembles the report.
- `src/geo_pulse/reporting/templates/report.html` defines document structure.
- `src/geo_pulse/reporting/templates/report.css` defines document presentation.
- `src/geo_pulse/tools/report_tool.py` exposes report generation to the agent.

### Required report sections

- Question and analysis scope
- Data sources and study period
- Included and excluded observations
- Feature definitions and units
- Model specification
- Key effects with uncertainty
- Predictive performance
- Spatial diagnostic results
- Correction history, if any
- Map and chart references
- Limitations and non-causal interpretation warning
- Reproducibility and run identifiers

The language model may phrase validated findings, but it must receive structured results and must not create coefficients, significance values, model scores, or facts that are absent from those results.

### Output

A report in `artifacts/reports/` and a publication manifest linking all associated artifacts.

## Stage 12: Return the final response

### Purpose

Return a concise, truthful result to the requesting interface.

### Responsible files

- `src/geo_pulse/agent/response_builder.py` assembles the final response.
- `src/geo_pulse/api/routes/analyses.py` returns status and findings.
- `src/geo_pulse/api/routes/reports.py` serves report and map artifacts.
- `src/geo_pulse/api/routes/models.py` exposes approved model metadata.
- `src/geo_pulse/storage/run_repository.py` records terminal status.

### Final response contents

- Completion status
- Direct answer to the original question
- Most important validated findings
- Key uncertainty and limitations
- Diagnostic outcome
- Model, report, and map identifiers
- Links or paths to generated artifacts

If diagnostics did not pass, the final response must say so prominently and avoid presenting the model as validated.

## Top-level pipeline ownership

`src/geo_pulse/pipelines/analysis_pipeline.py` owns the complete stage order. It does not implement domain calculations itself; it delegates to the five specialized pipelines:

1. `ingestion_pipeline.py` acquires and validates sources.
2. `feature_pipeline.py` prepares geography and engineers features.
3. `modeling_pipeline.py` builds datasets, trains models, evaluates, and predicts.
4. `correction_pipeline.py` handles bounded revisions after diagnostic failures.
5. `publishing_pipeline.py` builds maps, reports, manifests, and responses.

## Failure and recovery policy

Each stage must fail with a typed domain error from `core/exceptions.py`, record the failing stage and reason, preserve already completed artifacts, and avoid publishing partially valid findings as completed results.

Recoverable external-source failures may use configured retries and cached results. Data-quality, statistical, privacy, and unsupported-scope failures must not be bypassed through retries.

Resuming a run should begin at the earliest incomplete stage whose inputs and configuration still match the recorded lineage.

## Reproducibility requirements

A completed analysis should be reproducible from:

- Original request
- Accepted plan
- Configuration snapshots
- Source-data versions or checksums
- Feature catalog
- Model dataset version
- Model formula and grouping definition
- Random seed where relevant
- Software and dependency versions
- Correction history
- Artifact manifest

Generated files belong under `artifacts/`; source and derived datasets belong under `data/`. Neither should be silently committed to version control without an explicit project policy.

## Testing ownership

- `tests/unit/test_ingestion.py` will verify source normalization and validation.
- `tests/unit/test_gis.py` will verify coordinate systems, geometry operations, distances, and neighbor weights.
- `tests/unit/test_features.py` will verify feature values, units, missing-data rules, and lineage.
- `tests/unit/test_modeling.py` will verify formulas, fitting behavior, predictions, and metrics.
- `tests/unit/test_diagnostics.py` will verify diagnostic calculations and decisions.
- `tests/integration/test_analysis_pipeline.py` will verify stage order, artifacts, retries, and terminal states.
- `tests/integration/test_api.py` will verify request validation, run status, error behavior, and artifact access.
- `tests/fixtures/` will contain small synthetic records and boundaries with known expected behavior.

## Exploratory notebook roles

Notebooks support investigation and methodology development; they are not production pipeline stages.

- `notebooks/01_data_exploration.ipynb` explores coverage, missingness, distributions, and quality.
- `notebooks/02_spatial_features.ipynb` evaluates distance, density, projection, and accessibility definitions.
- `notebooks/03_mixed_effects_model.ipynb` compares hierarchical specifications and interpretation.
- `notebooks/04_spatial_diagnostics.ipynb` evaluates residual patterns, weights, and correction candidates.

Any accepted notebook discovery must be reimplemented in a deterministic source module and covered by tests before it becomes part of the production pipeline.

## Definition of done for a run

A Geo-Pulse analysis is complete only when:

- The request and plan are stored.
- All source and feature lineage is recorded.
- The model converged or the report clearly records why it did not.
- Required statistical and spatial diagnostics ran.
- Every correction attempt is documented.
- The terminal diagnostic decision is explicit.
- Required map and report artifacts were generated or their absence is explained.
- The final response states limitations and does not imply causality from observational associations.
- The run repository contains a terminal status and complete artifact manifest.
# Generic schema-adaptive entry path

Before the shared modeling stages, `analyze-spatial` performs:

1. **Inspect** — load the table, examine names and value types, and score candidate semantic roles.
2. **Map** — resolve an inferred or user-supplied `DatasetColumnMapping`.
3. **Standardize** — produce `record_id`, `target`, `latitude`, `longitude`, `group_id`, and formula-safe numeric fixed effects.
4. **Normalize CRS** — transform source coordinates or geometry into WGS84 and select a local UTM/azimuthal-equidistant metric CRS from the dataset center.
5. **Validate** — remove invalid coordinates and duplicate IDs, verify numeric target/features, and enforce the model's row/group requirements.
6. **Analyze** — reuse mixed-effects modeling, spatial correction, Moran's I diagnostics, mapping, and reporting.

The generic path intentionally skips property-age and amenity-distance engineering. The existing housing and free-public-data paths retain those specialized stages.

