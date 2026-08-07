import re

from geo_pulse.core.exceptions import ModelingError

SAFE_COLUMN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def validate_columns(columns: list[str]) -> list[str]:
    invalid = [column for column in columns if not SAFE_COLUMN.fullmatch(column)]
    if invalid:
        raise ModelingError(f"Unsafe model column names: {', '.join(invalid)}")
    return columns


def build_formula(target: str, fixed_effects: list[str]) -> str:
    validate_columns([target, *fixed_effects])
    if not fixed_effects:
        raise ModelingError("At least one fixed effect is required")
    return f"{target} ~ " + " + ".join(fixed_effects)
