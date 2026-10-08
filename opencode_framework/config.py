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


def host_npmrc_path() -> str:
    """Return the host ``~/.npmrc`` path when the file exists, else "".

    Used to populate ``OCF_NPMRC_PATH`` so the compose file can mirror the
    host npm configuration read-only into the container home.

    Returns:
        Absolute host path as a string, or "" when the file is absent.
    """
    candidate = get_local_home() / ".npmrc"
    return str(candidate) if candidate.is_file() else ""


def host_m2_settings_path(maven_installed: bool) -> str:
    """Return the host ``~/.m2/settings.xml`` path when applicable, else "".

    Used to populate ``OCF_M2_SETTINGS_PATH`` so the compose file can
    mirror the host Maven settings read-only into the container when the
    Maven feature is enabled.

    Args:
        maven_installed: Whether the Maven feature is enabled; the path
            is only reported when the feature is on.

    Returns:
        Absolute host path as a string, or "" when Maven is not
        installed or the file is absent.
    """
    if not maven_installed:
        return ""
    candidate = get_local_home() / ".m2" / "settings.xml"
    return str(candidate) if candidate.is_file() else ""


def host_gitconfig_path() -> str:
    """Return the host ``~/.gitconfig`` path when the file exists, else "".

    Used to populate ``OCF_GITCONFIG_PATH`` so the compose file can mirror
    the host git configuration (identity, aliases, ``insteadOf`` rewrites,
    ``safe.directory`` entries) read-only into the container home. The
    mirror is always on (npmrc pattern); host-only settings that cannot
    work inside the sandbox (``commit.gpgsign`` without GPG keys,
    credential-helper binaries, absolute ``[include]`` paths) are
    tolerated and fail loudly at git runtime.

    Returns:
        Absolute host path as a string, or "" when the file is absent.
    """
    candidate = get_local_home() / ".gitconfig"
    return str(candidate) if candidate.is_file() else ""


def host_ssh_dir_path(ssh_enabled: bool) -> str:
    """Return the host ``~/.ssh`` directory path when applicable, else "".

    Used to populate ``OCF_SSH_DIR_PATH`` so the compose file can mirror
    the host SSH material (keys, config, known_hosts) read-only into the
    container home when the ``ssh`` feature is enabled. Because the
    mirror target is a directory, no ``/dev/null`` fallback exists: the
    mount line is only emitted when this returns a non-empty path.

    Args:
        ssh_enabled: Whether the ssh feature is enabled; the path is
            only reported when the feature is on.

    Returns:
        Absolute host path as a string, or "" when the feature is off
        or the directory is absent.
    """
    if not ssh_enabled:
        return ""
    candidate = get_local_home() / ".ssh"
    return str(candidate) if candidate.is_dir() else ""


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
