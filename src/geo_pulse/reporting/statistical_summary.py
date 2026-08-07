from geo_pulse.schemas.models import DiagnosticSummary, ModelSummary


def coefficient_rows(model: ModelSummary) -> str:
    rows = []
    for item in model.coefficients:
        se = "" if item.standard_error is None else f"{item.standard_error:.6g}"
        p = "" if item.p_value is None else f"{item.p_value:.6g}"
        rows.append(
            f"<tr><td>{item.name}</td><td>{item.estimate:.6g}</td><td>{se}</td><td>{p}</td></tr>"
        )
    return "\n".join(rows)


def diagnostic_text(diagnostic: DiagnosticSummary) -> str:
    return (
        f"Moran's I={diagnostic.morans_i:.6g}; expected={diagnostic.expected_i:.6g}; "
        f"permutation p={diagnostic.p_value:.6g}; decision={diagnostic.decision}."
    )
