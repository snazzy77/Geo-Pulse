from pathlib import Path

import pandas as pd

from geo_pulse.schemas.models import ModelSummary


def write_coefficient_table(summary: ModelSummary, output_path: str | Path) -> Path:
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame([item.model_dump() for item in summary.coefficients]).to_csv(target, index=False)
    return target
