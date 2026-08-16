import math

import pandas as pd

from geo_pulse.agent.prompts import EPIDEMIOLOGY_AGENT_PROMPT
from geo_pulse.agent.surveillance_agent import (
    invoke_surveillance_agent,
    parse_surveillance_markdown,
)
from geo_pulse.schemas.models import Coefficient, DiagnosticSummary, ModelSummary


def _model_summary() -> ModelSummary:
    return ModelSummary(
        model_type="Bayesian Poisson GLMM with geographic random intercept",
        formula="target_y ~ industrial_exposure_score + census_percent_below_poverty",
        converged=True,
        row_count=40,
        group_count=4,
        metrics={"poisson_deviance": 30.0},
        coefficients=[
            Coefficient(name="Intercept", estimate=-2.0, standard_error=0.2, p_value=0.001),
            Coefficient(
                name="industrial_exposure_score",
                estimate=math.log(1.211),
                standard_error=0.05,
                p_value=0.012,
            ),
            Coefficient(
                name="census_percent_below_poverty",
                estimate=math.log(1.03),
                standard_error=0.03,
                p_value=0.21,
            ),
        ],
        random_effects={"C(group_id)[tract-a]": 0.3, "C(group_id)[tract-b]": -0.1},
        extra={"family": "Poisson"},
    )


def _diagnostic() -> DiagnosticSummary:
    return DiagnosticSummary(
        morans_i=0.24,
        expected_i=-0.03,
        p_value=0.01,
        permutations=199,
        passed=False,
        decision="REVIEW",
    )


def test_epidemiology_agent_interprets_irrs_clustering_and_named_outliers():
    predictions = pd.DataFrame(
        {
            "tract_fips": ["53033000101", "53033000200", "53033000300"],
            "target_y": [120, 90, 50],
            "predicted_target_y": [70, 72, 48],
            "residual": [50, 18, 2],
            "pearson_residual": [5.98, 2.12, 0.29],
            "surveillance_alert": [True, True, False],
        }
    )

    output = invoke_surveillance_agent(
        "How is industrial proximity associated with asthma?",
        _model_summary(),
        _diagnostic(),
        predictions,
    )

    assert any("IRR 1.211" in finding for finding in output.findings)
    assert any("21.1% increase" in finding for finding in output.findings)
    assert "significant positive residual spatial clustering" in output.spatial_diagnostics
    assert "53033000101" in output.spatial_diagnostics
    assert "Largest positive geographic random-intercept" in output.spatial_diagnostics
    assert output.top_outliers[0]["geography"] == "53033000101"
    assert "## Executive Summary" in output.markdown
    assert "## Environmental Exposure Evaluation" in output.markdown
    assert "## Socioeconomic Vulnerability Analysis" in output.markdown
    assert "## Surveillance Recommendations" in output.markdown
    assert "validated analytical output" in output.agent_payload.casefold()


def test_llm_markdown_parser_requires_explicit_findings_and_limitations_sections():
    markdown = """## FINDINGS
- IRR 1.20 was statistically significant.

## LIMITATIONS
- Exposure is a proximity proxy.
"""

    findings, limitations = parse_surveillance_markdown(markdown)

    assert findings == ["IRR 1.20 was statistically significant."]
    assert limitations == ["Exposure is a proximity proxy."]
    assert "never invent" in EPIDEMIOLOGY_AGENT_PROMPT.casefold()
