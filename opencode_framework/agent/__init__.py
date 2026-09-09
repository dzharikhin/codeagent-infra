"""Agent package: tool registry and config layers."""

from opencode_framework.agent.registry import (
    DEFAULT_TOOL,
    SUPPORTED_TOOLS,
    InstallSpec,
    ServeSpec,
    ToolSpec,
    get_tool_spec,
)

__all__ = [
    "DEFAULT_TOOL",
    "InstallSpec",
    "SUPPORTED_TOOLS",
    "ServeSpec",
    "ToolSpec",
    "get_tool_spec",
]
