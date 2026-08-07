import pandas as pd

from geo_pulse.core.exceptions import ModelingError
from geo_pulse.features.transformations import add_model_target, fill_numeric_medians


def build_model_dataset(
    frame: pd.DataFrame,
    target: str,
    group_column: str,
    fixed_effects: list[str],
    minimum_rows: int = 20,
    minimum_groups: int = 2,
    minimum_rows_per_group: int = 2,
    target_transform: str = "log",
) -> tuple[pd.DataFrame, str, str]:
    required = [target, group_column, "latitude", "longitude", *fixed_effects]
    missing = [column for column in required if column not in frame]
    if missing:
        raise ModelingError(f"Model dataset is missing columns: {', '.join(missing)}")
    data = fill_numeric_medians(frame, fixed_effects)
    data = data.dropna(subset=required).copy()
    group_sizes = data[group_column].value_counts()
    eligible = group_sizes[group_sizes >= minimum_rows_per_group].index
    data = data[data[group_column].isin(eligible)].reset_index(drop=True)
    if len(data) < minimum_rows:
        raise ModelingError(f"Model requires at least {minimum_rows} valid rows; found {len(data)}")
    if data[group_column].nunique() < minimum_groups:
        raise ModelingError(f"Model requires at least {minimum_groups} geographic groups")
    data, model_target, resolved_transform = add_model_target(data, target, target_transform)
    return data, model_target, resolved_transform
