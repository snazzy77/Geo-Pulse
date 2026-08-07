import html
from pathlib import Path

from geo_pulse.reporting.statistical_summary import coefficient_rows, diagnostic_text
from geo_pulse.schemas.models import DiagnosticSummary, ModelSummary


def build_report(
    question: str,
    executive_summary: str,
    findings: list[str],
    limitations: list[str],
    model: ModelSummary,
    diagnostic: DiagnosticSummary,
    map_path: Path,
    output_path: str | Path,
) -> Path:
    findings_html = "".join(f"<li>{html.escape(item)}</li>" for item in findings)
    limitations_html = "".join(f"<li>{html.escape(item)}</li>" for item in limitations)
    document = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>Geo-Pulse report</title><style>
body{{font-family:system-ui,sans-serif;max-width:1000px;margin:2rem auto;padding:0 1rem;color:#17202a}}
table{{border-collapse:collapse;width:100%}}th,td{{border:1px solid #ddd;padding:.5rem;text-align:left}}
.status{{padding:.75rem;background:#eef6ff;border-left:4px solid #2874a6}}
</style></head><body>
<h1>Geo-Pulse Analysis</h1><h2>Question</h2><p>{html.escape(question)}</p>
<div class="status">{html.escape(executive_summary)}</div>
<h2>Findings</h2><ul>{findings_html}</ul>
<h2>Model</h2><p>{html.escape(model.formula)}</p>
<table><thead><tr><th>Term</th><th>Estimate</th><th>Std. error</th><th>p-value</th></tr></thead>
<tbody>{coefficient_rows(model)}</tbody></table>
<h2>Spatial diagnostics</h2><p>{html.escape(diagnostic_text(diagnostic))}</p>
<h2>Limitations</h2><ul>{limitations_html}</ul>
<p><a href="{html.escape(map_path.as_posix())}">Open interactive map</a></p>
</body></html>"""
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(document, encoding="utf-8")
    return target
