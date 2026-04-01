"""Runtime helpers for launch and exec commands."""

import os
import re
from pathlib import Path
from typing import Tuple, Dict

from opencode_framework.preflight import is_inside_git_tree, get_repo_root
from opencode_framework.config import validate_framework_repo, get_framework_validation_error


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
    
    env = load_and_expand_env(env_file)
    framework_path_str = env.get("OCF_LOCAL_FRAMEWORK_PATH")
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


def load_and_expand_env(env_path: Path) -> Dict[str, str]:
    """Load .env file and expand variable references.
    
    Supports:
    - Simple KEY=VALUE lines
    - ${VAR} references
    - ${VAR:-default} syntax
    
    Expansion is done in order, so variables must be defined before use.
    
    Args:
        env_path: Path to the .env file
        
    Returns:
        Dictionary of expanded key-value pairs
    """
    result: Dict[str, str] = {}
    
    if not env_path.is_file():
        return result
    
    content = env_path.read_text()
    
    for line in content.splitlines():
        line = line.strip()
        
        if not line or line.startswith("#"):
            continue
        
        if "=" not in line:
            continue
        
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        
        if not key:
            continue
        
        expanded_value = _expand_value(value, result)
        result[key] = expanded_value
    
    return result


def _expand_value(value: str, env: Dict[str, str]) -> str:
    """Expand variable references in a value.
    
    Supports:
    - ${VAR} - expand to value of VAR
    - ${VAR:-default} - expand to value of VAR, or 'default' if not set
    """
    def replace_var(match: re.Match) -> str:
        var_expr = match.group(1)
        
        if ":-" in var_expr:
            var_name, default = var_expr.split(":-", 1)
            return env.get(var_name, default) or ""
        else:
            return env.get(var_expr, "") or ""
    
    pattern = r'\$\{([^}]+)\}'
    return re.sub(pattern, replace_var, value)


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
