from geo_pulse.schemas.models import DiagnosticSummary, ModelSummary


def build_executive_summary(
    question: str, model: ModelSummary, diagnostic: DiagnosticSummary
) -> str:
    quality = model.metrics.get("r_squared", 0.0)
    validation = "passed" if diagnostic.passed else "did not pass"
    return (
        f"Geo-Pulse analyzed {model.row_count} properties across {model.group_count} groups "
        f"for the question: {question} The fitted mixed-effects model had an in-sample "
        f"log-price R² of {quality:.3f}. Residual spatial diagnostics {validation}."
    )
