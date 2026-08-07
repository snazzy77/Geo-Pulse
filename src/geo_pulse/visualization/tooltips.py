import html

import pandas as pd


def property_tooltip(row: pd.Series, target: str) -> str:
    record_id = html.escape(str(row.get("property_id", row.get("record_id", "unknown"))))
    group = html.escape(str(row.get("neighborhood", row.get("group_id", "unknown"))))
    actual = float(row[target])
    predicted = float(row[f"predicted_{target}"])
    currency = target.lower() in {"price", "sale_price", "value"}
    actual_text = f"${actual:,.0f}" if currency else f"{actual:,.4g}"
    predicted_text = f"${predicted:,.0f}" if currency else f"{predicted:,.4g}"
    return (
        f"<b>Record:</b> {record_id}<br>"
        f"<b>Group:</b> {group}<br>"
        f"<b>Observed:</b> {actual_text}<br>"
        f"<b>Predicted:</b> {predicted_text}"
    )
