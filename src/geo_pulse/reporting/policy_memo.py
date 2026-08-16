from __future__ import annotations

from geo_pulse.schemas.models import DiagnosticSummary, ModelSummary


def build_policy_memo(
    question: str,
    model: ModelSummary,
    diagnostic: DiagnosticSummary,
    alert_count: int,
    alert_threshold: float = 2.0,
) -> tuple[str, list[str]]:
    exposure = next(
        (item for item in model.coefficients if item.name == "industrial_exposure_score"),
        None,
    )
    exposure_signal = bool(
        exposure
        and exposure.p_value is not None
        and exposure.p_value < 0.05
        and exposure.estimate > 0
    )
    residual_cluster = diagnostic.p_value < 0.05 and diagnostic.morans_i > 0
    if exposure_signal and not residual_cluster:
        assessment = "localized and consistent with measured industrial exposure"
        actions = [
            "Prioritize field validation and air monitoring around the highest-exposure tracts.",
            "Review emissions, permitting, and mitigation controls for nearby industrial sites.",
            "Direct respiratory outreach and clinical resources to tracts with active alerts.",
        ]
    elif residual_cluster:
        assessment = "spatially systemic or driven by unmeasured area-level conditions"
        actions = [
            "Investigate county-wide care access, reporting practices, weather, and mobile sources.",
            "Expand environmental monitoring before attributing the pattern to one hazard class.",
            "Coordinate surveillance methods across counties and neighboring jurisdictions.",
        ]
    else:
        assessment = "inconclusive with no single dominant spatial mechanism"
        actions = [
            "Continue surveillance and validate case definitions and reporting completeness.",
            "Add PM2.5, NO2, weather, smoking prevalence, and socioeconomic covariates.",
            "Avoid causal enforcement decisions until exposure and outcome timing are aligned.",
        ]
    memo = (
        "PUBLIC HEALTH SURVEILLANCE MEMO\n\n"
        f"Question: {question}\n\n"
        f"Assessment: The current pattern is {assessment}. "
        f"Geo-Pulse identified {alert_count} tract-level positive count anomalies at the "
        f"configured {alert_threshold:.1f}σ threshold. "
        f"Residual Moran's I is {diagnostic.morans_i:.3f} "
        f"(permutation p={diagnostic.p_value:.3f}).\n\n"
        "Recommended actions:\n"
        + "\n".join(f"- {item}" for item in actions)
        + "\n\nThis observational analysis is an early-warning aid, not proof of causation."
    )
    return memo, actions
