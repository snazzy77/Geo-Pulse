import pandas as pd

from geo_pulse.features.builder import build_features
from geo_pulse.schemas.features import FeatureSet


def run_feature_pipeline(
    properties: pd.DataFrame,
    amenities: pd.DataFrame,
    feature_config: dict,
) -> tuple[pd.DataFrame, FeatureSet]:
    return build_features(
        properties,
        amenities,
        list(feature_config.get("amenity_types", ["park"])),
        int(feature_config.get("density_radius_m", 1000)),
    )
