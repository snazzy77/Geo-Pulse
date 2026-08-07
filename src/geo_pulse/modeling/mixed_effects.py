from __future__ import annotations

import warnings
from dataclasses import dataclass

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf

from geo_pulse.core.exceptions import ModelingError
from geo_pulse.modeling.formula_builder import build_formula


@dataclass
class FittedModel:
    result: object
    formula: str
    target: str
    group_column: str
    fixed_effects: list[str]
    converged: bool
    warnings: list[str]
    fixed_only_prediction: bool = False
    is_mixed: bool = True
    model_type: str = "MixedLM random intercept"


def _usable_random_covariance(result: object) -> bool:
    covariance = np.atleast_2d(np.asarray(result.cov_re, dtype=float))
    if not np.isfinite(covariance).all():
        return False
    return bool(np.linalg.eigvalsh(covariance).min() > 1e-10)


def fit_group_fixed_effects(
    data: pd.DataFrame,
    target: str,
    group_column: str,
    fixed_effects: list[str],
    previous_warnings: list[str] | None = None,
) -> FittedModel:
    formula = build_formula(target, fixed_effects) + f" + C({group_column})"
    result = smf.ols(formula, data=data).fit()
    warning = (
        "The random-intercept variance reached a zero boundary with both MixedLM optimizers; "
        f"Geo-Pulse used {group_column} fixed effects for stable estimation and prediction."
    )
    return FittedModel(
        result=result,
        formula=formula,
        target=target,
        group_column=group_column,
        fixed_effects=fixed_effects,
        converged=True,
        warnings=list(dict.fromkeys([*(previous_warnings or []), warning])),
        is_mixed=False,
        model_type="OLS with geographic fixed effects (MixedLM boundary fallback)",
    )


def fit_mixed_effects(
    data: pd.DataFrame,
    target: str,
    group_column: str,
    fixed_effects: list[str],
) -> FittedModel:
    formula = build_formula(target, fixed_effects)
    model = smf.mixedlm(formula, data=data, groups=data[group_column], re_formula="1")
    errors: list[str] = []
    fit_warnings: list[str] = []
    boundary_found = False
    for method in ("lbfgs", "powell"):
        try:
            with warnings.catch_warnings(record=True) as captured:
                warnings.simplefilter("always")
                result = model.fit(method=method, reml=False, maxiter=500, disp=False)
            fit_warnings.extend(str(item.message) for item in captured)
            if np.isfinite(
                np.asarray(result.params, dtype=float)
            ).all() and _usable_random_covariance(result):
                return FittedModel(
                    result=result,
                    formula=formula,
                    target=target,
                    group_column=group_column,
                    fixed_effects=fixed_effects,
                    converged=bool(getattr(result, "converged", False)),
                    warnings=list(dict.fromkeys(fit_warnings)),
                )
            errors.append(f"{method}: random-effect covariance reached zero boundary")
            boundary_found = True
        except Exception as exc:  # noqa: BLE001 - optimizer backends raise varied exceptions
            errors.append(f"{method}: {exc}")
    if boundary_found:
        return fit_group_fixed_effects(data, target, group_column, fixed_effects, fit_warnings)
    raise ModelingError("Mixed-effects model failed: " + "; ".join(errors))
