import pandas as pd
import pytest

from geo_pulse.core.exceptions import DataValidationError
from geo_pulse.ingestion.validators import validate_properties


def test_validate_properties_removes_duplicate_ids(sample_paths):
    properties = pd.read_csv(sample_paths[0])
    duplicated = pd.concat([properties, properties.iloc[[0]]], ignore_index=True)
    clean = validate_properties(duplicated)
    assert len(clean) == len(properties)
    assert clean["property_id"].is_unique


def test_validate_properties_rejects_missing_schema():
    with pytest.raises(DataValidationError):
        validate_properties(pd.DataFrame({"price": [1]}))
