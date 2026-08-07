import pandas as pd

from geo_pulse.diagnostics.correction_policy import apply_default_correction


def run_correction_pipeline(
    frame: pd.DataFrame, fixed_effects: list[str]
) -> tuple[pd.DataFrame, list[str], str]:
    return apply_default_correction(frame, fixed_effects)
