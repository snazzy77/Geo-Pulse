import pandas as pd

from geo_pulse.features.builder import build_features


def test_feature_builder_adds_spatial_columns(sample_paths):
    properties = pd.read_csv(sample_paths[0])
    amenities = pd.read_csv(sample_paths[1])
    frame, feature_set = build_features(properties, amenities, ["park"], 1000)
    assert "dist_to_park_m" in frame
    assert "park_count_1000m" in frame
    assert (frame["dist_to_park_m"] >= 0).all()
    assert feature_set.row_count == len(properties)
