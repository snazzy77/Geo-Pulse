from collections.abc import Callable

from geo_pulse.tools.schema_tool import inspect_dataframe_schema_tool


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Callable] = {}

    def register(self, name: str, function: Callable) -> None:
        self._tools[name] = function

    def get(self, name: str) -> Callable:
        if name not in self._tools:
            raise KeyError(f"Unknown tool: {name}")
        return self._tools[name]

    def names(self) -> list[str]:
        return sorted(self._tools)


def default_tool_registry() -> ToolRegistry:
    registry = ToolRegistry()
    registry.register("inspect_dataframe_schema", inspect_dataframe_schema_tool)
    return registry
