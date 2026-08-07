from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CONFIG_DIR = PACKAGE_ROOT / "configs"
EARTH_RADIUS_M = 6_371_008.8
RUN_STATES = {
    "received",
    "planning",
    "ingesting",
    "engineering",
    "modeling",
    "diagnosing",
    "correcting",
    "publishing",
    "completed",
    "completed-with-limitations",
    "failed",
}
