# Epidemiological modeling methodology

Geo-Pulse's primary outcome is a non-negative integer count such as daily or weekly asthma cases, respiratory admissions, or emergency visits. Incoming source columns are mapped to the canonical `target_y`; county, ZIP, tract, or another repeated geography is mapped to `group_id`.

## Exposure engineering

Industrial facilities are converted to a local meter-based CRS and buffered by 2 km by default. Geo-Pulse spatially joins each outcome geography or point against those buffers. `industrial_exposure_score` is the number of overlapping hazard buffers, and `nearest_industrial_site_km` records proximity to the closest site. The buffer is a screening proxy, not a dispersion or dose model.

## Poisson GLMM

Count surveillance uses a log-link Poisson generalized linear mixed model:

```text
log(target_y) ~ industrial_exposure_score + socioeconomic/environmental covariates
                + (1 | group_id)
```

Geo-Pulse fits the model with `statsmodels.genmod.bayes_mixed_glm.PoissonBayesMixedGLM`. Coefficients are reported on the log-count scale; exponentiating a coefficient gives an estimated count rate ratio. Geographic random intercepts account for repeated observations within counties or other groups.

## Live PLACES tract model

The automated CDC PLACES workflow contains one cross-sectional estimate per tract. It therefore fits a Poisson GLM rather than claiming an identifiable tract random intercept:

```text
log(estimated_cases) ~ industrial_exposure_score + ACS controls
                       + offset(log(adult_population))
```

The fixed population offset models rates instead of raw counts. `estimated_cases` is the CDC modeled crude prevalence multiplied by PLACES `totalpop18plus` and rounded. It is an analytical approximation, not an observed case count. The 11-digit tract FIPS is the deterministic join key across PLACES, ACS, and TIGERweb.

## Surveillance and spatial diagnostics

Predicted counts and Pearson residuals are calculated for every record. Positive Pearson residuals at or above the configured 1–5σ threshold are early-warning alerts; the dashboard defaults to 2σ. Moran's I with permutation inference tests whether remaining residuals are spatially clustered. Outcome variance substantially larger than its mean triggers a recommendation for negative-binomial or zero-inflated sensitivity analysis.

Optional Census controls include median household income (scaled by $10,000), percent below poverty, and percent age 65+. Geo-Pulse discovers the newest available ACS 5-year release at run time and records the vintage in the schema manifest.

## Interpretation

The policy memo classifies a result as consistent with localized measured exposure, spatially systemic/unmeasured area conditions, or inconclusive. This is observational screening: alerts and associations do not establish diagnosis or causality and require epidemiological and environmental validation.

The surveillance interpretation agent receives structured coefficients rather than parsing formatted statsmodels prose. For each non-intercept fixed effect it calculates `IRR = exp(beta)` and `(IRR - 1) × 100%`, preserves the p-value, and states the covariate unit. Significant positive residual Moran's I is identified as unexplained clustering; negative or nonsignificant results are described separately. Named records are ranked by positive Pearson residual, with observed and expected counts retained for the three largest anomalies. For prevalence-derived PLACES counts, outputs are called adjusted rate ratios rather than literal incidence estimates.

The generic non-count workflow retains the earlier Gaussian mixed-effects model for continuous outcomes.
