import html

import pandas as pd


def property_tooltip(row: pd.Series, target: str) -> str:
    property_id = html.escape(str(row.get("property_id", "unknown")))
    neighborhood = html.escape(str(row.get("neighborhood", "unknown")))
    actual = float(row[target])
    predicted = float(row[f"predicted_{target}"])
    return (
        f"<b>Property:</b> {property_id}<br>"
        f"<b>Neighborhood:</b> {neighborhood}<br>"
        f"<b>Observed:</b> ${actual:,.0f}<br>"
        f"<b>Predicted:</b> ${predicted:,.0f}"
    )
