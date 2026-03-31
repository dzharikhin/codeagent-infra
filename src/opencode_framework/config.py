"""Configuration discovery and management."""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class GlobalSettings:
    """Detected global settings for the framework."""
    
    framework_repo_path: Optional[str]
    global_config_found: bool
    global_config_path: Optional[str]
    global_auth_found: bool
    global_auth_path: Optional[str]


def discover_global_settings() -> GlobalSettings:
    """Discover global settings at canonical paths.
    
    Looks for:
    - ~/.config/opencode - global config directory
    - ~/.local/share/opencode/auth.json - global auth file
    
    Does not prompt user for locations.
    """
    home = Path.home()
    
    global_config_dir = home / ".config" / "opencode"
    global_config_found = global_config_dir.is_dir()
    global_config_path = str(global_config_dir) if global_config_found else None
    
    global_auth_file = home / ".local" / "share" / "opencode" / "auth.json"
    global_auth_found = global_auth_file.is_file()
    global_auth_path = str(global_auth_file) if global_auth_found else None
    
    framework_repo_path = _detect_framework_repo_path()
    
    return GlobalSettings(
        framework_repo_path=framework_repo_path,
        global_config_found=global_config_found,
        global_config_path=global_config_path,
        global_auth_found=global_auth_found,
        global_auth_path=global_auth_path,
    )


def _detect_framework_repo_path() -> Optional[str]:
    """Detect the framework repository path from the installed package."""
    package_path = Path(__file__).resolve().parent
    
    repo_root = package_path.parent.parent
    if (repo_root / ".git").is_dir():
        return str(repo_root)
    
    return str(package_path)
