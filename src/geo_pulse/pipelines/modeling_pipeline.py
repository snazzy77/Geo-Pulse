import pandas as pd

from geo_pulse.modeling.dataset_builder import build_model_dataset
from geo_pulse.modeling.mixed_effects import FittedModel
from geo_pulse.modeling.trainer import train_model
from geo_pulse.schemas.models import ModelSummary


def run_modeling_pipeline(
    features: pd.DataFrame,
    target: str,
    group_column: str,
    fixed_effects: list[str],
    model_config: dict,
    target_transform: str = "log",
) -> tuple[pd.DataFrame, FittedModel, ModelSummary]:
    dataset, model_target, resolved_transform = build_model_dataset(
        features,
        target,
        group_column,
        fixed_effects,
        int(model_config.get("minimum_rows", 20)),
        int(model_config.get("minimum_groups", 2)),
        int(model_config.get("minimum_rows_per_group", 2)),
        target_transform,
    )
    fitted, predictions, summary = train_model(
        dataset, model_target, target, group_column, fixed_effects, resolved_transform
    )
    return predictions, fitted, summary
