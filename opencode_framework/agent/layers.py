"""Agent config layers: global-layer discovery, stubs, project layers.

Implements the layer wiring global < framework < project for each tool:
resolves the global layer (host config file/dir, with framework stub
fallback) and generates the qwen project layer (only-if-missing).
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from opencode_framework.config import (
    get_local_config_root,
    get_local_data_home,
    get_local_home,
)

from .registry import ToolSpec

QWEN_PROJECT_SETTINGS_STUB = "{}\n"


@dataclass
class GlobalLayer:
    """Resolved global layer for one tool."""

    global_found: bool
    global_path: Optional[str]
    auth_found: bool
    auth_path: Optional[str]
    stub_path: Optional[str]


def expected_global_path(
    spec: ToolSpec,
    config_root: Optional[Path] = None,
    home: Optional[Path] = None,
) -> Path:
    """Expected host path of a tool's global config (dir or file).

    Follows the spec's base/relpath fields; injectable roots override
    the host defaults (XDG-aware) for testing.
    """
    if spec.global_config_base == "config_root":
        base = config_root if config_root is not None else get_local_config_root()
    else:
        base = home if home is not None else get_local_home()
    return base.joinpath(*spec.global_config_relpath)


def expected_global_env_path(
    spec: ToolSpec,
    config_root: Optional[Path] = None,
    home: Optional[Path] = None,
) -> Path:
    """Expected host path of a tool's global .env file.

    Follows the spec's global_config_base and global_env_relpath
    (e.g. ~/.config/opencode/.env for opencode, ~/.qwen/.env for
    qwen); injectable roots override the host defaults (XDG-aware)
    for testing.
    """
    if spec.global_config_base == "config_root":
        base = config_root if config_root is not None else get_local_config_root()
    else:
        base = home if home is not None else get_local_home()
    return base.joinpath(*spec.global_env_relpath)


def discover_global_layer(
    spec: ToolSpec,
    config_root: Optional[Path] = None,
    data_home: Optional[Path] = None,
    home: Optional[Path] = None,
    framework_repo_path: Optional[str] = None,
) -> GlobalLayer:
    """Discover the global layer for a tool.

    Resolves the tool's global config location (dir for opencode, file
    for qwen) and, where applicable, the auth file. Paths follow the
    spec's base/relpath fields; injectable roots override the host
    defaults (XDG-aware) for testing. The framework stub fallback path
    is derived from the framework repo when known.

    Args:
        spec: tool spec providing location shape.
        config_root: override for the config root (default:
            $XDG_CONFIG_HOME or ~/.config).
        data_home: override for the data home (default: $XDG_DATA_HOME
            or ~/.local/share).
        home: override for the user home.
        framework_repo_path: framework repo root, enables stub
            fallback resolution.

    Returns:
        Resolved GlobalLayer with found flags and paths.
    """
    global_path = expected_global_path(spec, config_root=config_root, home=home)
    if spec.global_config_is_dir:
        global_found = global_path.is_dir()
    else:
        global_found = global_path.is_file()

    auth_path: Optional[Path] = None
    auth_found = False
    if spec.auth_relpath is not None:
        auth_root = data_home if data_home is not None else get_local_data_home()
        auth_candidate = auth_root.joinpath(*spec.auth_relpath)
        auth_found = auth_candidate.is_file()
        if auth_found:
            auth_path = auth_candidate

    stub_path: Optional[str] = None
    if framework_repo_path:
        stub_path = str(
            Path(framework_repo_path).joinpath("framework-config", *spec.stub_relpath)
        )

    return GlobalLayer(
        global_found=global_found,
        global_path=str(global_path) if global_found else None,
        auth_found=auth_found,
        auth_path=str(auth_path) if auth_path else None,
        stub_path=stub_path,
    )


def ensure_project_layer(spec: ToolSpec, repo_root: Path) -> Optional[Path]:
    """Create the tool's project layer at the repo root, if it has one.

    Only-if-missing by design: existing files are never overwritten, so
    ``init --force`` preserves user edits. Tools without a generated
    project layer (opencode uses the .opencode/ worktree) are no-ops.

    Args:
        spec: tool spec identifying the tool.
        repo_root: project repository root.

    Returns:
        Path to the created settings file, or None when it already
        existed or the tool has no project layer.
    """
    if spec.name == "qwen":
        return ensure_qwen_project_layer(repo_root)
    return None


def ensure_qwen_project_layer(repo_root: Path) -> Optional[Path]:
    """Create the qwen project layer (``.qwen/settings.json``) if absent.

    Only-if-missing by design: an existing file is never overwritten,
    so ``init --force`` preserves user edits.

    Args:
        repo_root: project repository root.

    Returns:
        Path to the created settings file, or None when it already
        existed.
    """
    settings_path = repo_root / ".qwen" / "settings.json"
    if settings_path.exists():
        return None
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings_path.write_text(QWEN_PROJECT_SETTINGS_STUB)
    return settings_path
