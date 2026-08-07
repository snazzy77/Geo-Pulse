import pandas as pd

from geo_pulse.diagnostics.assumptions import check_assumptions
from geo_pulse.diagnostics.morans_i import morans_i
from geo_pulse.diagnostics.residuals import residual_vector
from geo_pulse.gis.geometries import coordinate_array
from geo_pulse.gis.spatial_weights import knn_weights
from geo_pulse.schemas.models import DiagnosticSummary


def run_diagnostics(
    predictions: pd.DataFrame,
    fixed_effects: list[str],
    converged: bool,
    k_neighbors: int = 5,
    permutations: int = 199,
    alpha: float = 0.05,
    seed: int = 42,
    can_retry: bool = True,
) -> tuple[DiagnosticSummary, list[str]]:
    weights = knn_weights(coordinate_array(predictions), k_neighbors)
    result = morans_i(residual_vector(predictions), weights, permutations, seed)
    warnings = check_assumptions(predictions, fixed_effects, converged)
    passed = converged and result.p_value >= alpha
    decision = "PASS" if passed else ("REVISE" if can_retry else "STOP")
    return DiagnosticSummary(
        morans_i=result.statistic,
        expected_i=result.expected,
        p_value=result.p_value,
        permutations=result.permutations,
        passed=passed,
        decision=decision,
    ), warnings
