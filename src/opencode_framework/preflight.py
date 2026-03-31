"""Preflight checks and repository validation."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional
import shutil
import subprocess


@dataclass
class PreflightResult:
    """Result of preflight checks."""
    
    success: bool
    error: Optional[str] = None
    remediation: Optional[str] = None
    repo_root: Optional[Path] = None
    has_staged_changes: bool = False
    is_bare_repo: bool = False
    is_inside_git_tree: bool = False
    missing_tools: List[str] = field(default_factory=list)
    docker_rootless_available: bool = False
    
    def __post_init__(self):
        if self.missing_tools is None:
            self.missing_tools = []


REQUIRED_TOOLS = ["git", "docker", "devcontainer", "pipx"]


def check_required_tools() -> List[str]:
    """Check that all required tools are available.
    
    Returns list of missing tool names.
    """
    missing = []
    for tool in REQUIRED_TOOLS:
        if shutil.which(tool) is None:
            missing.append(tool)
    return missing


def check_docker_rootless_context() -> bool:
    """Check if a rootless Docker context exists.
    
    Returns True if rootless context is available.
    """
    try:
        result = subprocess.run(
            ["docker", "context", "ls", "--format", "{{.Name}}"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            contexts = result.stdout.strip().split("\n")
            return "rootless" in contexts
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    return False


def run_git_command(args: List[str], cwd: Optional[Path] = None) -> tuple[int, str, str]:
    """Run a git command and return (returncode, stdout, stderr)."""
    try:
        result = subprocess.run(
            ["git"] + args,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=30,
        )
        return result.returncode, result.stdout.strip(), result.stderr.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        return -1, "", str(e)


def is_inside_git_tree(path: Path) -> bool:
    """Check if path is inside a Git working tree."""
    returncode, _, _ = run_git_command(["rev-parse", "--is-inside-work-tree"], cwd=path)
    return returncode == 0


def is_bare_repository(path: Path) -> bool:
    """Check if the repository is bare."""
    returncode, stdout, _ = run_git_command(["rev-parse", "--is-bare-repository"], cwd=path)
    return returncode == 0 and stdout.lower() == "true"


def get_repo_root(path: Path) -> Optional[Path]:
    """Get the repository root directory."""
    returncode, stdout, _ = run_git_command(["rev-parse", "--show-toplevel"], cwd=path)
    if returncode == 0 and stdout:
        return Path(stdout)
    return None


def has_staged_changes(path: Path) -> bool:
    """Check if the Git index has staged changes."""
    returncode, stdout, _ = run_git_command(["diff", "--cached", "--quiet"], cwd=path)
    return returncode != 0


def opencode_directory_exists(repo_root: Path) -> bool:
    """Check if .opencode/ directory already exists."""
    return (repo_root / ".opencode").exists()


def run_preflight_checks(cwd: Path, force: bool = False) -> PreflightResult:
    """Run all preflight checks.
    
    Validates:
    - Required tools are present
    - Current directory is inside a Git working tree
    - Current directory is the repository root
    - Repository is not bare
    - Git index has no staged changes
    - .opencode/ doesn't exist (unless --force)
    """
    missing_tools = check_required_tools()
    if missing_tools:
        return PreflightResult(
            success=False,
            error=f"Missing required tools: {', '.join(missing_tools)}",
            remediation=f"Install missing tools: {' '.join(missing_tools)}",
            missing_tools=missing_tools,
        )
    
    if not is_inside_git_tree(cwd):
        return PreflightResult(
            success=False,
            error="Current directory is not inside a Git working tree",
            remediation="Run this command from inside a Git repository",
        )
    
    repo_root = get_repo_root(cwd)
    if repo_root is None:
        return PreflightResult(
            success=False,
            error="Could not determine repository root",
            remediation="Ensure you are in a valid Git repository",
        )
    
    if repo_root != cwd.resolve():
        return PreflightResult(
            success=False,
            error="Current directory is not the repository root",
            remediation=f"Run this command from the repository root: {repo_root}",
        )
    
    if is_bare_repository(cwd):
        return PreflightResult(
            success=False,
            error="Repository is bare (no working tree)",
            remediation="Use a non-bare repository with a working tree",
        )
    
    if has_staged_changes(cwd):
        return PreflightResult(
            success=False,
            error="Git index has staged changes",
            remediation="Commit or unstage your changes before running init",
            has_staged_changes=True,
        )
    
    if opencode_directory_exists(repo_root):
        if not force:
            return PreflightResult(
                success=False,
                error=".opencode/ already exists",
                remediation="Use --force to backup and regenerate, or remove it manually",
            )
    
    return PreflightResult(
        success=True,
        repo_root=repo_root,
        is_inside_git_tree=True,
        is_bare_repo=False,
    )
