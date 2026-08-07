import pandas as pd

from geo_pulse.ingestion.schema_mapper import inspect_dataframe_schema
from geo_pulse.schemas.datasets import SchemaInspection


def inspect_dataframe_schema_tool(
    frame: pd.DataFrame, aliases: dict[str, list[str]] | None = None
) -> SchemaInspection:
    """Agent-facing tool for discovering semantic roles in a new spatial table."""
    return inspect_dataframe_schema(frame, aliases)
