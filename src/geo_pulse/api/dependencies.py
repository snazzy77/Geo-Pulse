from functools import lru_cache

from geo_pulse.core.config import Settings, load_settings


@lru_cache
def get_settings() -> Settings:
    return load_settings()
