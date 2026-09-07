"""Sandbox package: tool-agnostic container isolation.

Owns the devcontainer image build, Docker Compose runtime, mounts,
networks, ports, and the environment variables of this layer. Never
imports tool-specific knowledge; the agent tool registry fills the
agent slots.
"""

from opencode_framework.sandbox.compose import ComposeGenerator
from opencode_framework.sandbox.devcontainer import (
    DevcontainerGenerator,
    detect_devcontainer,
    evaluate_compatibility,
)
from opencode_framework.sandbox.features import update_features
from opencode_framework.sandbox.net import find_free_port
from opencode_framework.sandbox.runtime import EnvError

__all__ = [
    "ComposeGenerator",
    "DevcontainerGenerator",
    "EnvError",
    "detect_devcontainer",
    "evaluate_compatibility",
    "find_free_port",
    "update_features",
]
