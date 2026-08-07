import pandas as pd

from geo_pulse.ingestion.schema_mapper import inspect_dataframe_schema, standardize_dataset
from geo_pulse.schemas.datasets import DatasetColumnMapping


def test_inspector_maps_non_housing_spatial_dataset():
    frame = pd.DataFrame(
        {
            "Case Number": [f"case-{index}" for index in range(24)],
            "Disease Rate": [3.0 + index * 0.2 for index in range(24)],
            "Lat": [41.8 + index * 0.001 for index in range(24)],
            "Lng": [-87.7 + index * 0.001 for index in range(24)],
            "Community Area": [f"area-{index % 4}" for index in range(24)],
            "Pollution Exposure": [10 + index for index in range(24)],
            "Median Income": [50_000 + index * 500 for index in range(24)],
        }
    )

    inspection = inspect_dataframe_schema(frame)

    assert inspection.suggested_mapping is not None
    assert inspection.suggested_mapping.target_variable == "Disease Rate"
    assert inspection.suggested_mapping.group_col == "Community Area"
    assert inspection.suggested_mapping.id_col == "Case Number"
    assert inspection.suggested_mapping.fixed_features == [
        "Pollution Exposure",
        "Median Income",
    ]


def test_standardizer_handles_wkt_and_unsafe_feature_names():
    frame = pd.DataFrame(
        {
            "Outcome Rate": [1.2, 2.4],
            "Area Name": ["north", "south"],
            "Geometry": ["POINT (-0.12 51.50)", "POINT (-0.10 51.52)"],
            "PM 2.5": [8.0, 12.0],
        }
    )
    mapping = DatasetColumnMapping(
        target_variable="Outcome Rate",
        group_col="Area Name",
        geometry_col="Geometry",
        fixed_features=["PM 2.5"],
    )

    standardized, fixed_effects = standardize_dataset(frame, mapping)

    assert fixed_effects == ["pm_2_5"]
    assert standardized["latitude"].between(51.49, 51.53).all()
    assert standardized["longitude"].between(-0.13, -0.09).all()
    assert list(standardized["record_id"]) == ["record-1", "record-2"]


def test_standardizer_converts_projected_xy_to_wgs84():
    frame = pd.DataFrame(
        {
            "value": [1.0, 2.0],
            "district": ["a", "b"],
            "x": [0.0, 111_319.4908],
            "y": [0.0, 111_325.1429],
            "exposure": [4.0, 5.0],
        }
    )
    mapping = DatasetColumnMapping(
        target_variable="value",
        group_col="district",
        lat_col="y",
        lon_col="x",
        fixed_features=["exposure"],
        source_crs="EPSG:3857",
    )

    standardized, _ = standardize_dataset(frame, mapping)

    assert abs(standardized.loc[0, "latitude"]) < 1e-6
    assert abs(standardized.loc[0, "longitude"]) < 1e-6
    assert abs(standardized.loc[1, "latitude"] - 1.0) < 1e-4
    assert abs(standardized.loc[1, "longitude"] - 1.0) < 1e-4
