import math

from geo_pulse.schemas.models import DiagnosticSummary, ModelSummary


def generate_findings(model: ModelSummary, diagnostic: DiagnosticSummary) -> list[str]:
    findings: list[str] = []
    transform = str(model.extra.get("target_transform", "log"))
    outcome = "the log-transformed target" if transform == "log" else "the target"
    for coefficient in model.coefficients:
        if (
            coefficient.name == "Intercept"
            or coefficient.p_value is None
            or not math.isfinite(coefficient.estimate)
            or not math.isfinite(coefficient.p_value)
            or coefficient.p_value >= 0.05
        ):
            continue
        direction = "higher" if coefficient.estimate > 0 else "lower"
        findings.append(
            f"{coefficient.name} is associated with {direction} {outcome} "
            f"(estimate {coefficient.estimate:.4g}, p={coefficient.p_value:.3g})."
        )
    findings.append(
        f"Residual Moran's I was {diagnostic.morans_i:.3f} "
        f"(permutation p={diagnostic.p_value:.3f}); diagnostic decision: {diagnostic.decision}."
    )
    return findings
