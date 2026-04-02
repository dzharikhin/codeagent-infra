"""Configuration management module."""

import os
import pwd
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple, List

from opencode_framework.exceptions import ConfigurationError


@dataclass
class GlobalSettings:
    """Detected global settings for the framework."""
    
    framework_repo_path: Optional[str]
    framework_config_path: Optional[str]
    global_config_found: bool
    global_config_path: Optional[str]
    global_auth_found: bool
    global_auth_path: Optional[str]


class ConfigManager:
    """Manages configuration discovery and validation."""
    
    # Required paths for a valid framework repository
    REQUIRED_FRAMEWORK_PATHS = [
        ".git",
        "framework-nuts-and-bolts",
        "framework-config",
        "framework-nuts-and-bolts/stub-auth.json",
    ]
    
    @staticmethod
    def get_local_home() -> Path:
        """Get the local user's home directory.
        
        Respects the actual local user context, not the process user.
        Precedence:
        1. SUDO_USER's home if running under sudo
        2. HOME environment variable
        3. Current user's home from passwd
        
        Returns:
            Path to home directory
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
    
    @staticmethod
    def get_local_config_root() -> Path:
        """Get the local config root directory.
        
        This is used for creating and discovering the host's global config.
        Respects XDG_CONFIG_HOME from the local environment.
        
        Returns:
            Path to config root
        """
        xdg_config = os.environ.get("XDG_CONFIG_HOME")
        if xdg_config:
            return Path(xdg_config)
        
        return ConfigManager.get_local_home() / ".config"
    
    @staticmethod
    def get_local_data_home() -> Path:
        """Get the local data home directory.
        
        Respects XDG_DATA_HOME from the local environment.
        
        Returns:
            Path to data home
        """
        xdg_data = os.environ.get("XDG_DATA_HOME")
        if xdg_data:
            return Path(xdg_data)
        
        return ConfigManager.get_local_home() / ".local" / "share"
    
    @staticmethod
    def validate_framework_repo(path: Path) -> Tuple[bool, List[str]]:
        """Validate that a path is a valid framework repository.
        
        Checks for required paths:
        - .git/
        - framework-nuts-and-bolts/
        - framework-config/
        - framework-nuts-and-bolts/stub-auth.json
        
        Args:
            path: Path to validate
            
        Returns:
            Tuple of (is_valid, missing_paths)
        """
        missing = []
        for required in ConfigManager.REQUIRED_FRAMEWORK_PATHS:
            req_path = path / required
            if required.endswith(".json"):
                if not req_path.is_file():
                    missing.append(required)
            else:
                if not req_path.is_dir():
                    missing.append(required)
        
        return len(missing) == 0, missing
    
    @staticmethod
    def get_framework_validation_error(
        missing: List[str],
        framework_path: Optional[str],
    ) -> str:
        """Generate a clear error message for invalid framework repo.
        
        Args:
            missing: List of missing required paths
            framework_path: Detected framework path
            
        Returns:
            Error message string
        """
        msg = "Framework repository is not valid or not installed correctly.\n"
        msg += f"Detected path: {framework_path or 'none'}\n"
        if missing:
            msg += f"Missing required paths: {', '.join(missing)}\n"
        msg += "\nThe framework must be installed as an editable package from a git clone:\n"
        msg += "  pipx install -e <path-to-framework-git-clone>\n"
        msg += "\nClone the framework repository first, then install it with pipx."
        return msg
    
    @staticmethod
    def detect_framework_repo_path() -> Optional[str]:
        """Detect the framework repository path from an editable install.
        
        Only returns a path if it is a valid framework git clone with all
        required directories and files. Returns None if not installed from
        a framework git clone.
        
        The framework MUST be installed via:
            pipx install -e <path-to-framework-git-clone>
        
        Returns:
            Framework repo path or None
        """
        package_path = Path(__file__).resolve().parent
        repo_root = package_path.parent.parent
        
        valid, _ = ConfigManager.validate_framework_repo(repo_root)
        if valid:
            return str(repo_root)
        
        return None
    
    @staticmethod
    def detect_framework_config_path(
        framework_repo_path: Optional[str],
    ) -> Optional[str]:
        """Detect the framework config directory path.
        
        Args:
            framework_repo_path: Path to framework repository
            
        Returns:
            Config path or None
        """
        if not framework_repo_path:
            return None
        
        config_path = Path(framework_repo_path) / "framework-config"
        if config_path.is_dir():
            return str(config_path)
        
        return None
    
    @staticmethod
    def discover_global_settings() -> GlobalSettings:
        """Discover global settings at canonical paths.
        
        Looks for:
        - $XDG_CONFIG_HOME/opencode or ~/.config/opencode - global config directory
        - $XDG_DATA_HOME/opencode/auth.json or ~/.local/share/opencode/auth.json - global auth file
        - framework config/ directory
        
        Uses local user context (respects SUDO_USER, HOME env) for host-side paths.
        Does not prompt user for locations.
        
        Returns:
            GlobalSettings with detected configuration
        """
        config_root = ConfigManager.get_local_config_root()
        global_config_dir = config_root / "opencode"
        global_config_found = global_config_dir.is_dir()
        global_config_path = str(global_config_dir) if global_config_found else None
        
        data_home = ConfigManager.get_local_data_home()
        global_auth_file = data_home / "opencode" / "auth.json"
        global_auth_found = global_auth_file.is_file()
        global_auth_path = str(global_auth_file) if global_auth_found else None
        
        framework_repo_path = ConfigManager.detect_framework_repo_path()
        framework_config_path = ConfigManager.detect_framework_config_path(
            framework_repo_path
        )
        
        return GlobalSettings(
            framework_repo_path=framework_repo_path,
            framework_config_path=framework_config_path,
            global_config_found=global_config_found,
            global_config_path=global_config_path,
            global_auth_found=global_auth_found,
            global_auth_path=global_auth_path,
        )
