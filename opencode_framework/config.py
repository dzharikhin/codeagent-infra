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


def discover_global_settings() -> GlobalSettings:
    """Discover global settings for the framework installation.

    Uses local user context (respects SUDO_USER, HOME env) for
    host-side paths. Does not prompt user for locations.
    """
    return GlobalSettings(
        framework_repo_path=_detect_framework_repo_path(),
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
