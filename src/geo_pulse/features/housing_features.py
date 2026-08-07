from datetime import UTC, datetime

import pandas as pd


def add_housing_features(frame: pd.DataFrame, analysis_year: int | None = None) -> pd.DataFrame:
    result = frame.copy()
    year = analysis_year or datetime.now(UTC).year
    if "year_built" in result:
        built = pd.to_numeric(result["year_built"], errors="coerce")
        median = built.median() if built.notna().any() else year
        result["property_age"] = (year - built.fillna(median)).clip(lower=0)
    else:
        result["property_age"] = 0.0
    return result
