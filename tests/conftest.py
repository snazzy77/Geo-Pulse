from pathlib import Path

import pytest

from geo_pulse.core.config import load_settings
from geo_pulse.sample_data import generate_sample_data


@pytest.fixture
def sample_paths(tmp_path: Path) -> tuple[Path, Path]:
    return generate_sample_data(tmp_path / "sample")


@pytest.fixture
def test_settings():
    settings = load_settings()
    settings.models = dict(settings.models)
    settings.models["morans_permutations"] = 19
    return settings
