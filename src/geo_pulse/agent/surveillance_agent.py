from __future__ import annotations

import json
import math
from collections.abc import Callable
from dataclasses import dataclass

import pandas as pd

from geo_pulse.agent.prompts import EPIDEMIOLOGY_AGENT_PROMPT
from geo_pulse.schemas.models import Coefficient, DiagnosticSummary, ModelSummary


@dataclass(slots=True)
class SurveillanceAgentOutput:
    executive_summary: str
    environmental_exposure_evaluation: str
    socioeconomic_vulnerability_analysis: str
    spatial_diagnostics: str
    surveillance_recommendations: list[str]
    findings: list[str]
    limitations: list[str]
    top_outliers: list[dict[str, object]]
    markdown: str
    agent_payload: str


def _p_value(value: float | None) -> str:
    if value is None or not math.isfinite(value):
        return "not available"
    return "<0.001" if value < 0.001 else f"{value:.3f}"


def _term_context(name: str) -> tuple[str, str]:
    contexts = {
        "industrial_exposure_score": (
            "industrial buffer exposure",
            "each additional overlapping industrial hazard buffer",
        ),
        "nearest_industrial_site_km": (
            "distance to the nearest industrial site",
            "each additional kilometer from the nearest industrial site",
        ),
        "census_median_household_income_10k": (
            "median household income",
            "each $10,000 increase in median household income",
        ),
        "census_percent_below_poverty": (
            "poverty prevalence",
            "each one-percentage-point increase below the poverty line",
        ),
        "census_percent_age_65_plus": (
            "older-adult population share",
            "each one-percentage-point increase in residents age 65 or older",
        ),
    }
    return contexts.get(name, (name.replace("_", " "), f"each one-unit increase in {name}"))


def _effect_interpretation(coefficient: Coefficient, prevalence_derived: bool) -> str:
    label, unit = _term_context(coefficient.name)
    irr = math.exp(coefficient.estimate)
    percent = (irr - 1) * 100
    direction = "increase" if percent >= 0 else "decrease"
    outcome = "expected modeled count rate" if prevalence_derived else "expected event rate"
    significance = (
        "statistically significant at α=0.05"
        if coefficient.p_value is not None and coefficient.p_value < 0.05
        else "not statistically significant at α=0.05"
    )
    return (
        f"{label.title()}: IRR {irr:.3f} (β={coefficient.estimate:.3f}, "
        f"p={_p_value(coefficient.p_value)}). {unit.capitalize()} corresponds to a "
        f"{abs(percent):.1f}% {direction} in the {outcome}, holding modeled covariates "
        f"constant; this association is {significance}."
    )


def _top_outliers(predictions: pd.DataFrame, limit: int = 3) -> list[dict[str, object]]:
    geography_column = next(
        (
            column
            for column in ("tract_fips", "group_id", "record_id", "county_fips")
            if column in predictions
        ),
        None,
    )
    residual_column = (
        "pearson_residual" if "pearson_residual" in predictions else "residual"
    )
    if geography_column is None or residual_column not in predictions:
        return []
    ranked = predictions.copy()
    ranked[residual_column] = pd.to_numeric(ranked[residual_column], errors="coerce")
    ranked = ranked[ranked[residual_column].gt(0)].nlargest(limit, residual_column)
    output: list[dict[str, object]] = []
    for _, row in ranked.iterrows():
        item: dict[str, object] = {
            "geography": str(row[geography_column]),
            "pearson_residual": float(row[residual_column]),
        }
        if "residual" in ranked:
            item["residual"] = float(row["residual"])
        if "target_y" in ranked:
            item["observed"] = float(row["target_y"])
        if "predicted_target_y" in ranked:
            item["expected"] = float(row["predicted_target_y"])
        output.append(item)
    return output


def _outlier_text(outliers: list[dict[str, object]]) -> str:
    if not outliers:
        return "No named positive-residual geography was available for ranking."
    entries = []
    for item in outliers:
        detail = f"{item['geography']} (Pearson residual {item['pearson_residual']:.2f}"
        if "observed" in item and "expected" in item:
            detail += f", observed {item['observed']:.1f}, expected {item['expected']:.1f}"
        entries.append(detail + ")")
    return "Highest positive-residual geographies: " + "; ".join(entries) + "."


def _random_effect_text(model: ModelSummary) -> str:
    if not model.random_effects:
        return (
            "No geographic random intercepts were estimated in this specification; the live "
            "cross-sectional tract workflow uses a population-offset GLM."
        )
    ranked = sorted(model.random_effects.items(), key=lambda item: item[1], reverse=True)[:3]
    values = "; ".join(f"{name} ({value:+.3f})" for name, value in ranked)
    return (
        "Largest positive geographic random-intercept estimates were "
        + values
        + ". These identify residual area-level variation, not causal effects."
    )


def _agent_payload(
    question: str,
    model: ModelSummary,
    diagnostic: DiagnosticSummary,
    outliers: list[dict[str, object]],
) -> str:
    payload = {
        "research_question": question,
        "statistical_model": model.model_dump(mode="json"),
        "spatial_diagnostics": diagnostic.model_dump(mode="json"),
        "top_positive_residual_geographies": outliers,
    }
    return (
        "-- RESEARCH QUESTION AND VALIDATED ANALYTICAL OUTPUT --\n"
        + json.dumps(payload, indent=2)
        + "\n\nGenerate the required epidemiological findings, limitations, and report sections."
    )


def parse_surveillance_markdown(markdown: str) -> tuple[list[str], list[str]]:
    """Extract dashboard bullets from an optional provider-generated Markdown response."""
    sections: dict[str, list[str]] = {"findings": [], "limitations": []}
    current: str | None = None
    for raw_line in markdown.splitlines():
        line = raw_line.strip()
        heading = line.lstrip("#").strip().casefold().rstrip(":")
        if heading in sections:
            current = heading
            continue
        if current and line.startswith(("- ", "* ")):
            sections[current].append(line[2:].strip())
    return sections["findings"], sections["limitations"]


def invoke_surveillance_agent(
    research_question: str,
    glmm_results: ModelSummary,
    morans_i_p_value: DiagnosticSummary,
    df_outliers: pd.DataFrame,
    *,
    base_limitations: list[str] | None = None,
    llm: Callable[[str, str], str] | None = None,
) -> SurveillanceAgentOutput:
    """Interpret validated surveillance outputs and optionally route them through an LLM.

    The deterministic interpretation remains authoritative. If a provider callback is supplied,
    only its FINDINGS and LIMITATIONS bullets are parsed, and the computed fallback is retained
    whenever either required section is absent.
    """
    model = glmm_results
    diagnostic = morans_i_p_value
    outliers = _top_outliers(df_outliers)
    prevalence_derived = model.extra.get("offset_column") == "adult_population"
    fixed_effects = [item for item in model.coefficients if item.name != "Intercept"]
    effect_findings = [_effect_interpretation(item, prevalence_derived) for item in fixed_effects]
    exposure = next(
        (item for item in fixed_effects if item.name == "industrial_exposure_score"), None
    )
    socioeconomic = [
        item
        for item in fixed_effects
        if item.name
        in {
            "census_median_household_income_10k",
            "census_percent_below_poverty",
            "census_percent_age_65_plus",
        }
    ]
    outlier_sentence = _outlier_text(outliers)
    random_effect_sentence = _random_effect_text(model)
    if diagnostic.p_value < 0.05 and diagnostic.morans_i > 0:
        spatial = (
            f"Residual Moran's I was {diagnostic.morans_i:.3f} "
            f"(permutation p={diagnostic.p_value:.3f}), indicating significant positive residual "
            "spatial clustering and potential unmeasured hot spots requiring investigation. "
            + outlier_sentence
            + " "
            + random_effect_sentence
        )
    elif diagnostic.p_value < 0.05:
        spatial = (
            f"Residual Moran's I was {diagnostic.morans_i:.3f} "
            f"(permutation p={diagnostic.p_value:.3f}), indicating significant spatial "
            "dispersion rather than positive hot-spot clustering. "
            + outlier_sentence
            + " "
            + random_effect_sentence
        )
    else:
        spatial = (
            f"Residual Moran's I was {diagnostic.morans_i:.3f} "
            f"(permutation p={diagnostic.p_value:.3f}); residual spatial clustering was not "
            "statistically significant at α=0.05. "
            + outlier_sentence
            + " "
            + random_effect_sentence
        )

    if exposure is None:
        environmental = "The fitted specification did not contain industrial exposure."
        exposure_support = "could not evaluate the specified industrial-exposure relationship"
    else:
        environmental = _effect_interpretation(exposure, prevalence_derived)
        significant = exposure.p_value is not None and exposure.p_value < 0.05
        exposure_support = (
            "found statistical support for an industrial-exposure association"
            if significant
            else "did not find statistically significant support for an industrial-exposure association"
        )
    socioeconomic_text = (
        " ".join(_effect_interpretation(item, prevalence_derived) for item in socioeconomic)
        if socioeconomic
        else "No ACS socioeconomic fixed effects were included in this fitted specification."
    )
    anomaly_count = int(df_outliers.get("surveillance_alert", pd.Series(dtype=bool)).sum())
    executive = (
        f"Geo-Pulse {exposure_support} for the studied data and identified {anomaly_count} "
        "positive surveillance alerts. Results are observational risk signals, not evidence of "
        "causation or individual diagnosis."
    )
    recommendations = [
        *(
            [
                "Prioritize confirmatory record review and mobile air monitoring in "
                + ", ".join(str(item["geography"]) for item in outliers)
                + "."
            ]
            if outliers
            else ["Validate geography identifiers before directing place-specific resources."]
        ),
        "Review emissions inventories, traffic sources, wind, weather, and monitoring coverage before attributing risk to OSM hazards.",
        "Repeat the model with temporally aligned observed health events and negative-binomial sensitivity analysis when available.",
    ]
    findings = [*effect_findings[:5], spatial]
    limitations = list(
        dict.fromkeys(
            [
                *(base_limitations or []),
                "Rate ratios describe adjusted associations and do not establish causation.",
                "Industrial buffer overlap is a proximity proxy and does not model atmospheric plume dispersion or individual dose.",
            ]
        )
    )
    payload = _agent_payload(research_question, model, diagnostic, outliers)
    if llm is not None:
        provider_markdown = llm(EPIDEMIOLOGY_AGENT_PROMPT, payload)
        parsed_findings, parsed_limitations = parse_surveillance_markdown(provider_markdown)
        if parsed_findings:
            findings = parsed_findings
        if parsed_limitations:
            limitations = list(dict.fromkeys([*parsed_limitations, *limitations]))
    markdown = (
        "# Geo-Pulse Environmental Health Surveillance Report\n\n"
        f"## Research Question\n\n{research_question}\n\n"
        f"## Executive Summary\n\n{executive}\n\n"
        f"## Environmental Exposure Evaluation\n\n{environmental}\n\n"
        f"## Socioeconomic Vulnerability Analysis\n\n{socioeconomic_text}\n\n"
        f"## Spatial Diagnostics and Anomalous Geographies\n\n{spatial}\n\n"
        "## Surveillance Recommendations\n\n"
        + "\n".join(f"- {item}" for item in recommendations)
        + "\n\n## Findings\n\n"
        + "\n".join(f"- {item}" for item in findings)
        + "\n\n## Limitations\n\n"
        + "\n".join(f"- {item}" for item in limitations)
        + "\n"
    )
    return SurveillanceAgentOutput(
        executive_summary=executive,
        environmental_exposure_evaluation=environmental,
        socioeconomic_vulnerability_analysis=socioeconomic_text,
        spatial_diagnostics=spatial,
        surveillance_recommendations=recommendations,
        findings=findings,
        limitations=limitations,
        top_outliers=outliers,
        markdown=markdown,
        agent_payload=payload,
    )
