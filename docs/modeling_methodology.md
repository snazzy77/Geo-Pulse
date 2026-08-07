# Modeling Methodology

The default target is log sale price. Geo-Pulse fits a Statsmodels mixed linear model with configured property and spatial variables as fixed effects and a random intercept for the configured geographic grouping.

The MVP reports in-sample RMSE, MAE, and R² on the log-price scale. These metrics are descriptive and must not be treated as out-of-sample validation.

Residual spatial autocorrelation is evaluated using a row-standardized, symmetrized k-nearest-neighbor matrix and a reproducible permutation test for global Moran's I. A configured p-value threshold controls the diagnostic decision.

When diagnostics require revision, the default bounded correction adds centered latitude and longitude trend controls and retrains once. Every attempt is recorded. The correction is not a search for statistical significance and does not establish causality.
