# Environmental-health data dictionary

## Health outcome input

- Outcome count: aliases include `asthma_cases`, `respiratory_cases`, `hospital_admissions`, `emergency_visits`, `case_count`, and `cases`. It becomes canonical `target_y` and must be a non-negative integer.
- Geographic group: county, county FIPS, ZIP, census tract, district, or another repeated area. It becomes `group_id`.
- Location: WGS84 latitude/longitude or point/polygon geometry.
- Record ID: tract-period, facility-period, or surveillance-record identifier.
- Covariates: numeric environmental and socioeconomic fields such as PM2.5, NO2, deprivation, income, population, smoking prevalence, or care access.

## Environmental hazard input

Hazard files require latitude/longitude or geometry. OpenStreetMap sources include industrial zones, factories/works, refineries, and power plants. Names, operators, feature type, and source lineage are preserved when available.

## Engineered fields

- `tract_fips`: 11-digit Census tract identifier shared by CDC PLACES, ACS, and TIGERweb.
- `prevalence_pct`: CDC PLACES modeled crude adult prevalence for the selected measure.
- `adult_population`: PLACES `totalpop18plus`; used as the live model's population offset.
- `estimated_cases`: rounded `prevalence_pct / 100 × adult_population`; not an observed case log.
- `industrial_exposure_score`: number of configured industrial buffers intersecting a health record.
- `nearest_industrial_site_km`: distance to the closest hazard site.
- `predicted_target_y`: expected count from the selected Poisson GLMM or population-offset GLM.
- `residual`: observed minus expected count.
- `pearson_residual`: count residual standardized by the square root of the expected count.
- `surveillance_alert`: true when the positive Pearson residual reaches the configured threshold.
- `census_median_household_income_10k`: latest ACS median income scaled by $10,000.
- `census_percent_below_poverty`: latest ACS population percentage below poverty.
- `census_percent_age_65_plus`: latest ACS population percentage age 65 or older.
- `current_pm2_5` and `current_nitrogen_dioxide`: optional current Open-Meteo readings; these must be temporally aligned before substantive inference.

Legacy real-estate input contracts remain implemented for backward compatibility but are no longer the primary Geo-Pulse trajectory.
