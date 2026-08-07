import importlib
import sys

from geo_pulse.core.config import load_settings

if __name__ == "__main__":
    required = ["fastapi", "folium", "numpy", "pandas", "pydantic", "scipy", "statsmodels", "typer"]
    missing = []
    for package in required:
        try:
            importlib.import_module(package)
        except ImportError:
            missing.append(package)
    settings = load_settings()
    print(f"Python: {sys.version.split()[0]}")
    print(f"Project root: {settings.project_root}")
    print("Dependencies: " + ("missing " + ", ".join(missing) if missing else "OK"))
    raise SystemExit(1 if missing else 0)
