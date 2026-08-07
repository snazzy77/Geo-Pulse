from geo_pulse.schemas.models import DiagnosticSummary, ModelSummary


def build_executive_summary(
    question: str, model: ModelSummary, diagnostic: DiagnosticSummary
) -> str:
    quality = model.metrics.get("r_squared", 0.0)
    validation = "passed" if diagnostic.passed else "did not pass"
    transform = str(model.extra.get("target_transform", "log"))
    scale = "log-transformed target" if transform == "log" else "target"
    return (
        f"Geo-Pulse analyzed {model.row_count} spatial records across {model.group_count} groups "
        f"for the question: {question} The fitted mixed-effects model had an in-sample "
        f"{scale} R² of {quality:.3f}. Residual spatial diagnostics {validation}."
    )
