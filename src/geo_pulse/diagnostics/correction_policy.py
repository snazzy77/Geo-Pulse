import pandas as pd

from geo_pulse.modeling.spatial_model import add_spatial_controls


def apply_default_correction(
    frame: pd.DataFrame, fixed_effects: list[str]
) -> tuple[pd.DataFrame, list[str], str]:
    corrected, added = add_spatial_controls(frame)
    revised = [*fixed_effects, *[name for name in added if name not in fixed_effects]]
    return corrected, revised, "Added centered latitude and longitude trend controls"
