from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

from geo_pulse.core.constants import DEFAULT_CONFIG_DIR, PACKAGE_ROOT
from geo_pulse.core.exceptions import ConfigurationError


@dataclass(slots=True)
class Settings:
    project_root: Path = PACKAGE_ROOT
    environment: str = "development"
    data_dir: Path = Path("data")
    artifact_dir: Path = Path("artifacts")
    cache_dir: Path = Path(".cache")
    random_seed: int = 42
    log_level: str = "INFO"
    features: dict[str, Any] = field(default_factory=dict)
    models: dict[str, Any] = field(default_factory=dict)
    data_sources: dict[str, Any] = field(default_factory=dict)

    def resolve(self, value: str | Path) -> Path:
        path = Path(value)
        return path if path.is_absolute() else self.project_root / path

    @property
    def artifacts(self) -> Path:
        return self.resolve(self.artifact_dir)


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise ConfigurationError(f"Missing configuration file: {path}")
    with path.open("r", encoding="utf-8") as stream:
        return yaml.safe_load(stream) or {}


def load_settings(config_dir: str | Path = DEFAULT_CONFIG_DIR) -> Settings:
    config_path = Path(config_dir).resolve()
    load_dotenv(config_path.parent / ".env")
    app = _read_yaml(config_path / "app.yaml")
    settings = Settings(
        project_root=config_path.parent,
        environment=app.get("environment", "development"),
        data_dir=Path(app.get("data_dir", "data")),
        artifact_dir=Path(app.get("artifact_dir", "artifacts")),
        cache_dir=Path(app.get("cache_dir", ".cache")),
        random_seed=int(app.get("random_seed", 42)),
        log_level=str(app.get("log_level", "INFO")),
        features=_read_yaml(config_path / "features.yaml"),
        models=_read_yaml(config_path / "models.yaml"),
        data_sources=_read_yaml(config_path / "data_sources.yaml"),
    )
    settings.artifacts.mkdir(parents=True, exist_ok=True)
    settings.resolve(settings.cache_dir).mkdir(parents=True, exist_ok=True)
    return settings
