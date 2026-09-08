"""Configuration discovery and management."""

import os
import pwd
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


def get_local_home() -> Path:
    """Get the local user's home directory.

    Respects the actual local user context, not the process user.
    Precedence:
    1. SUDO_USER's home if running under sudo
    2. HOME environment variable
    3. Current user's home from passwd
    """
    sudo_user = os.environ.get("SUDO_USER")
    if sudo_user:
        try:
            return Path(pwd.getpwnam(sudo_user).pw_dir)
        except KeyError:
            pass

    home_env = os.environ.get("HOME")
    if home_env:
        return Path(home_env)

    return Path.home()


def get_local_config_root() -> Path:
    """Get the local config root directory for host-side operations.

    This is used for creating and discovering the host's global config.
    Respects XDG_CONFIG_HOME from the local environment.
    """
    xdg_config = os.environ.get("XDG_CONFIG_HOME")
    if xdg_config:
        return Path(xdg_config)

    return get_local_home() / ".config"


def get_local_data_home() -> Path:
    """Get the local data home directory.

    Respects XDG_DATA_HOME from the local environment.
    """
    xdg_data = os.environ.get("XDG_DATA_HOME")
    if xdg_data:
        return Path(xdg_data)

    return get_local_home() / ".local" / "share"


@dataclass
class GlobalSettings:
    """Detected global settings for the framework."""

    framework_repo_path: Optional[str]
    framework_config_path: Optional[str]
    global_config_found: bool
    global_config_path: Optional[str]
    global_auth_found: bool
    global_auth_path: Optional[str]


def get_config_root() -> Path:
    """Get the config root directory for host-side operations.

    Alias for get_local_config_root().
    Respects XDG_CONFIG_HOME from the local environment.
    Uses local user context (SUDO_USER, HOME env).
    """
    return get_local_config_root()


def discover_global_settings() -> GlobalSettings:
    """Discover global settings at canonical paths.

    Looks for:
    - $XDG_CONFIG_HOME/opencode or ~/.config/opencode - global config directory
    - $XDG_DATA_HOME/opencode/auth.json or ~/.local/share/opencode/auth.json - global auth file
    - framework config/ directory

    Uses local user context (respects SUDO_USER, HOME env) for host-side paths.
    Does not prompt user for locations.
    """
    config_root = get_local_config_root()
    global_config_dir = config_root / "opencode"
    global_config_found = global_config_dir.is_dir()
    global_config_path = str(global_config_dir) if global_config_found else None

    data_home = get_local_data_home()
    global_auth_file = data_home / "opencode" / "auth.json"
    global_auth_found = global_auth_file.is_file()
    global_auth_path = str(global_auth_file) if global_auth_found else None

    framework_repo_path = _detect_framework_repo_path()
    framework_config_path = _detect_framework_config_path(framework_repo_path)

    return GlobalSettings(
        framework_repo_path=framework_repo_path,
        framework_config_path=framework_config_path,
        global_config_found=global_config_found,
        global_config_path=global_config_path,
        global_auth_found=global_auth_found,
        global_auth_path=global_auth_path,
    )


def _detect_framework_repo_path() -> Optional[str]:
    """Detect the framework repository path from an editable install.

    Returns a path only when the package lives at the root of a git
    clone (a ``.git`` directory next to the package). Returns None
    otherwise.

    The framework is installed via:
        pipx install -e <path-to-framework-git-clone>
    """
    package_path = Path(__file__).resolve().parent

    repo_root = package_path.parent

    if (repo_root / ".git").is_dir():
        return str(repo_root)

    return None


def _detect_framework_config_path(framework_repo_path: Optional[str]) -> Optional[str]:
    """Detect the framework config directory path."""
    if not framework_repo_path:
        return None

    config_path = Path(framework_repo_path) / "framework-config"
    if config_path.is_dir():
        return str(config_path)

    return None
