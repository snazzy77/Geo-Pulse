import pandas as pd

from geo_pulse.features.feature_catalog import default_catalog
from geo_pulse.features.housing_features import add_housing_features
from geo_pulse.features.spatial_features import add_spatial_features
from geo_pulse.schemas.features import FeatureSet


def build_features(
    properties: pd.DataFrame,
    amenities: pd.DataFrame,
    amenity_types: list[str],
    density_radius_m: int,
) -> tuple[pd.DataFrame, FeatureSet]:
    frame = add_housing_features(properties)
    frame = add_spatial_features(frame, amenities, amenity_types, density_radius_m)
    catalog = default_catalog(amenity_types, density_radius_m)
    return frame, FeatureSet(
        columns=[item.name for item in catalog], catalog=catalog, row_count=len(frame)
    )
