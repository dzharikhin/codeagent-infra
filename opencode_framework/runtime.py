"""Runtime helpers for launch and exec commands."""

import os
import re
from pathlib import Path
from typing import Tuple, Dict, Optional, List

from dotenv import dotenv_values

from opencode_framework.preflight import is_inside_git_tree, get_repo_root
from opencode_framework.config import validate_framework_repo, get_framework_validation_error


class EnvError(Exception):
    """Base exception for environment loading errors with file/line context."""
    
    def __init__(
        self,
        message: str,
        file_path: Optional[Path] = None,
        line_num: Optional[int] = None,
    ):
        self.file_path = file_path
        self.line_num = line_num
        
        # Build full error message with context
        if file_path:
            prefix = str(file_path)
            if line_num:
                prefix += f":{line_num}"
            message = f"{prefix}: {message}"
        
        super().__init__(message)


class CircularReferenceError(EnvError):
    """Raised when circular references are detected in interpolation."""
    pass


class InterpolationError(EnvError):
    """Raised when interpolation fails."""
    pass


def validate_runtime_context(cwd: Path) -> Tuple[bool, str]:
    """Validate that the current directory is suitable for launch/exec.
    
    Checks:
    - Inside a Git working tree
    - At the repository root
    - .opencode/ directory exists
    - .opencode/devcontainer.json exists
    - .opencode/.env exists
    - Framework repo from .env still exists and is valid
    
    Returns:
        (True, "") on success
        (False, "error message") on failure
    """
    if not is_inside_git_tree(cwd):
        return False, "Current directory is not inside a Git working tree"
    
    repo_root = get_repo_root(cwd)
    if repo_root is None:
        return False, "Could not determine repository root"
    
    if repo_root != cwd.resolve():
        return False, f"Current directory is not the repository root. Run from: {repo_root}"
    
    opencode_dir = repo_root / ".opencode"
    if not opencode_dir.is_dir():
        return False, ".opencode/ directory does not exist. Run 'ocframework init' first."
    
    devcontainer_json = opencode_dir / "devcontainer.json"
    if not devcontainer_json.is_file():
        return False, ".opencode/devcontainer.json does not exist. Run 'ocframework init' first."
    
    env_file = opencode_dir / ".env"
    if not env_file.is_file():
        return False, ".opencode/.env does not exist. Run 'ocframework init' first."
    
    # Load base env to validate framework path
    try:
        base_env = dotenv_values(env_file, interpolate=True)
    except Exception as e:
        return False, f"Error reading .opencode/.env: {e}"
    
    framework_path_str = base_env.get("OCF_LOCAL_FRAMEWORK_PATH")
    if not framework_path_str:
        return False, "OCF_LOCAL_FRAMEWORK_PATH not set in .opencode/.env. Run 'ocframework init' again."
    
    framework_path = Path(framework_path_str)
    if not framework_path.exists():
        return False, (
            f"Framework repository no longer exists at: {framework_path_str}\n"
            "The framework must be reinstalled from a valid git clone:\n"
            "  pipx install -e <path-to-framework-git-clone>"
        )
    
    valid, missing = validate_framework_repo(framework_path)
    if not valid:
        error_msg = get_framework_validation_error(missing, framework_path_str)
        return False, f"Framework repository is invalid:\n{error_msg}"
    
    return True, ""


def load_env_with_overrides(
    base_env_path: Path,
    override_env_path: Optional[Path] = None,
    cli_env_vars: Optional[List[str]] = None,
) -> Dict[str, str]:
    """Load environment with proper precedence and interpolation.
    
    Uses python-dotenv for parsing, then applies recursive interpolation
    across all sources together.
    
    Precedence (lowest to highest):
    1. Base .env file
    2. Override file (if provided)
    3. CLI environment variables
    
    Supports:
    - Comments (#)
    - Export statements (export KEY=VALUE)
    - Basic interpolation: $VAR and ${VAR}
    - Default values: ${VAR:-default}
    - Escaped characters and quoted values
    
    Args:
        base_env_path: Path to base .env file
        override_env_path: Optional override env file
        cli_env_vars: Optional list of KEY=VALUE strings from CLI
        
    Returns:
        Merged and interpolated environment dictionary
        
    Raises:
        EnvError: For any loading or parsing errors
        CircularReferenceError: For circular references
        FileNotFoundError: If specified files don't exist
    """
    merged_env = {}
    
    # 1. Load base environment using python-dotenv (without interpolation first)
    if base_env_path.exists():
        try:
            # Load raw without interpolation
            base_env = dotenv_values(base_env_path, interpolate=False)
            # Convert None to empty string (dotenv returns None for some cases)
            base_env = {k: v if v is not None else "" for k, v in base_env.items()}
            merged_env.update(base_env)
        except Exception as e:
            raise EnvError(f"Failed to parse env file: {e}", file_path=base_env_path)
    
    # 2. Load override file if provided
    if override_env_path:
        if not override_env_path.exists():
            raise FileNotFoundError(f"Override env file not found: {override_env_path}")
        try:
            override_env = dotenv_values(override_env_path, interpolate=False)
            override_env = {k: v if v is not None else "" for k, v in override_env.items()}
            merged_env.update(override_env)
        except Exception as e:
            raise EnvError(f"Failed to parse env file: {e}", file_path=override_env_path)
    
    # 3. Parse CLI variables
    if cli_env_vars:
        try:
            cli_env = parse_cli_env_vars(cli_env_vars)
            merged_env.update(cli_env)
        except ValueError as e:
            raise EnvError(f"Invalid CLI environment variable: {e}")
    
    # 4. Apply recursive interpolation to merged environment
    # This handles both basic interpolation ($VAR, ${VAR}) and defaults (${VAR:-default})
    try:
        final_env = apply_combined_interpolation(merged_env, max_depth=5)
    except CircularReferenceError:
        raise
    except Exception as e:
        raise InterpolationError(f"Interpolation failed: {e}")
    
    return final_env


def parse_cli_env_vars(env_vars: List[str]) -> Dict[str, str]:
    """Parse KEY=VALUE pairs from command line.
    
    Note: Shell variables like $HOME are already expanded by shell.
    
    Args:
        env_vars: List of KEY=VALUE strings
        
    Returns:
        Parsed dictionary
        
    Raises:
        ValueError: For invalid format
    """
    result = {}
    
    for i, env_var in enumerate(env_vars, 1):
        if '=' not in env_var:
            raise ValueError(
                f"Argument {i}: '{env_var}' - expected KEY=VALUE format"
            )
        
        key, _, value = env_var.partition('=')
        key = key.strip()
        
        if not key:
            raise ValueError(
                f"Argument {i}: '{env_var}' - key cannot be empty"
            )
        
        # Validate key format (alphanumeric + underscores)
        if not key.replace('_', '').isalnum():
            raise ValueError(
                f"Argument {i}: '{env_var}' - key must be alphanumeric with underscores"
            )
        
        result[key] = value
    
    return result


def apply_combined_interpolation(
    env: Dict[str, str],
    max_depth: int = 5,
) -> Dict[str, str]:
    """Apply combined interpolation for all variable reference styles.
    
    Handles:
    - $VAR and ${VAR} basic references
    - ${VAR:-default} with default values
    
    Works recursively across the merged environment to resolve transitive
    references and enforce depth limits with circular reference detection.
    
    Args:
        env: Environment dictionary to interpolate
        max_depth: Maximum recursion depth
        
    Returns:
        Fully interpolated dictionary
        
    Raises:
        CircularReferenceError: If circular refs detected
        InterpolationError: If max depth exceeded
    """
    result = env.copy()
    
    # Pattern for all variable references: $VAR, ${VAR}, and ${VAR:-default}
    var_pattern = re.compile(r'\$\{?([A-Za-z_][A-Za-z0-9_]*(?:-[^}]*)?)?\}?|\$([A-Za-z_][A-Za-z0-9_]*)')
    
    for depth in range(max_depth):
        changed = False
        unresolved = set()
        
        for key, value in list(result.items()):
            if not isinstance(value, str):
                continue
            
            # Check if has variable syntax ($VAR or ${VAR})
            if '$' not in value:
                continue
            
            unresolved.add(key)
            new_value = _expand_all_variables(value, result, key)
            
            if new_value != value:
                result[key] = new_value
                changed = True
                # If fully resolved, remove from unresolved
                if '$' not in new_value:
                    unresolved.discard(key)
        
        if not changed:
            break
        
        # Check for circular references
        if depth > 0 and unresolved:
            # Check if values are stuck (haven't changed from original)
            stuck = all(result[k] == env[k] for k in unresolved)
            if stuck:
                raise CircularReferenceError(
                    f"Circular references in: {', '.join(sorted(unresolved))}"
                )
    else:
        # Max depth reached
        remaining = [k for k, v in result.items() if isinstance(v, str) and '$' in v]
        if remaining:
            raise InterpolationError(
                f"Max depth {max_depth} exceeded. Unresolved: {', '.join(remaining)}"
            )
    
    return result


def _expand_all_variables(value: str, env: Dict[str, str], current_key: str) -> str:
    """Expand all variable reference styles: $VAR, ${VAR}, ${VAR:-default}.
    
    Args:
        value: String with potential patterns
        env: Environment dictionary
        current_key: Current key (to avoid self-reference)
        
    Returns:
        Expanded string
    """
    def replace_var(match: re.Match) -> str:
        # Handle ${...} style
        if match.group(1) is not None:
            expr = match.group(1)
            
            # Handle ${VAR:-default} syntax
            if ':-' in expr:
                var_name, default = expr.split(':-', 1)
                var_name = var_name.strip()
                
                # Avoid self-reference
                if var_name == current_key:
                    return default
                
                # Get value or use default
                val = env.get(var_name, '')
                return val if val else default
            else:
                # Handle simple ${VAR}
                var_name = expr.strip()
                
                # Avoid self-reference
                if var_name == current_key:
                    return match.group(0)  # Leave as-is
                
                # Get value (leave unresolved if not found, for next pass)
                return env.get(var_name, '')
        
        # Handle $VAR style (simple reference)
        elif match.group(2) is not None:
            var_name = match.group(2)
            
            # Avoid self-reference
            if var_name == current_key:
                return match.group(0)  # Leave as-is
            
            # Get value
            return env.get(var_name, '')
        
        return match.group(0)
    
    # Match: ${VAR}, ${VAR:-default}, or $VAR
    pattern = re.compile(r'\$\{([^}]+)\}|\$([A-Za-z_][A-Za-z0-9_]*)')
    return pattern.sub(replace_var, value)





def build_devcontainer_env(
    base_env: Dict[str, str],
    docker_context: str,
) -> Dict[str, str]:
    """Build environment for devcontainer subprocess.
    
    Merges base_env with current process environment and sets DOCKER_CONTEXT.
    
    Args:
        base_env: Environment variables from .opencode/.env
        docker_context: Docker context to use (e.g., "rootless")
        
    Returns:
        Complete environment dict for subprocess
    """
    result = dict(os.environ)
    result.update(base_env)
    result["DOCKER_CONTEXT"] = docker_context
    return result


def identify_resolved_variables(
    base_env: Dict[str, str],
    resolved_env: Dict[str, str],
    cli_vars: Optional[Dict[str, str]] = None,
) -> Dict[str, str]:
    """Identify variables that were resolved or changed.
    
    Returns variables that:
    - Were specified on CLI (-e flags)
    - Contained ${...} or $VAR syntax in base_env and were resolved
    
    Args:
        base_env: Raw environment from .env file (before resolution)
        resolved_env: Environment after interpolation
        cli_vars: Variables from CLI (-e flags)
        
    Returns:
        Dictionary of variables to pass as --remote-env
    """
    cli_vars = cli_vars or {}
    resolved_vars = dict(cli_vars)
    
    for key, resolved_value in resolved_env.items():
        if key in base_env:
            base_value = base_env[key]
            if '${' in str(base_value) or (('$' in str(base_value) and key not in cli_vars)):
                if base_value != resolved_value:
                    resolved_vars[key] = resolved_value
    
    return resolved_vars


def add_remote_env_to_command(
    cmd: List[str],
    resolved_vars: Dict[str, str],
) -> List[str]:
    """Add resolved variables as --remote-env flags to devcontainer command.
    
    Args:
        cmd: Devcontainer command list
        resolved_vars: Dictionary of variables to add
        
    Returns:
        Modified command list with --remote-env flags
    """
    for key, value in resolved_vars.items():
        cmd.extend(["--remote-env", f"{key}={value}"])
    return cmd
