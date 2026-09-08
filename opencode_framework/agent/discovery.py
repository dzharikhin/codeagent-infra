"""Discovery of per-tool framework config directories.

Each supported tool owns one config directory at the repo root
(``ToolSpec.config_dirname``: ``.opencode`` for opencode, ``.qwen``
for qwen). A directory qualifies as a framework config when it
contains a ``.env``. The ``OCF_AGENT_TOOL`` value inside that ``.env``
must agree with the directory-implied tool; mismatches (legacy or
hand-edited layouts) are reported as invalid and excluded from
launch, with re-init as remediation.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

from dotenv import dotenv_values

from .registry import SUPPORTED_TOOLS, ToolSpec

AGENT_TOOL_KEY = "OCF_AGENT_TOOL"


@dataclass(frozen=True)
class ConfigLocation:
    """One discovered framework config directory.

    Attributes:
        spec: ToolSpec implied by the directory name.
        config_dir: absolute path of the config directory.
        env_tool: ``OCF_AGENT_TOOL`` value read from the directory's
            ``.env``, or None when absent/unreadable/empty.
    """

    spec: ToolSpec
    config_dir: Path
    env_tool: Optional[str] = None

    @property
    def valid(self) -> bool:
        """True when the .env tool agrees with the directory-implied tool."""
        return self.env_tool == self.spec.name


def read_env_agent_tool(config_dir: Path) -> Optional[str]:
    """Read ``OCF_AGENT_TOOL`` from a config directory's ``.env``.

    Args:
        config_dir: candidate config directory.

    Returns:
        The stripped value, or None when the file is missing,
        unreadable, or the key is absent/empty.
    """
    env_path = config_dir / ".env"
    if not env_path.is_file():
        return None
    try:
        parsed: Dict[str, Optional[str]] = dotenv_values(env_path, interpolate=False)
    except Exception:
        return None
    value = (parsed.get(AGENT_TOOL_KEY) or "").strip()
    return value or None


def discover_configs(repo_root: Path) -> List[ConfigLocation]:
    """Discover framework config directories for all supported tools.

    A directory qualifies when it contains a ``.env``; the tool it
    serves is implied by the directory name and cross-checked against
    ``OCF_AGENT_TOOL``. Both valid and invalid locations are returned;
    callers filter on :attr:`ConfigLocation.valid` and surface
    re-init remediation for invalid ones.

    Args:
        repo_root: project repository root.

    Returns:
        Discovered locations sorted by tool name.
    """
    locations: List[ConfigLocation] = []
    for name in sorted(SUPPORTED_TOOLS):
        spec = SUPPORTED_TOOLS[name]
        config_dir = repo_root / spec.config_dirname
        if not (config_dir / ".env").is_file():
            continue
        locations.append(
            ConfigLocation(
                spec=spec,
                config_dir=config_dir,
                env_tool=read_env_agent_tool(config_dir),
            )
        )
    return locations
