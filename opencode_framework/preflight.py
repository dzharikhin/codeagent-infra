"""Preflight checks and repository validation."""

import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from opencode_framework.agent.registry import DEFAULT_TOOL, get_tool_spec
from opencode_framework.config import _detect_framework_repo_path
from opencode_framework.git_ops import (
    get_repo_root,
    has_staged_changes,
    is_bare_repository,
    is_inside_git_tree,
)


@dataclass
class PreflightResult:
    """Result of preflight checks."""

    success: bool
    error: Optional[str] = None
    remediation: Optional[str] = None
    missing_tools: List[str] = field(default_factory=list)


REQUIRED_TOOLS = ["git", "docker", "devcontainer"]


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


def config_directory_exists(repo_root: Path, agent_tool: str = DEFAULT_TOOL) -> bool:
    """Check if the agent tool's config worktree directory already exists."""
    return (repo_root / get_tool_spec(agent_tool).config_dirname).exists()


def run_preflight_checks(
    cwd: Path, force: bool = False, agent_tool: str = DEFAULT_TOOL
) -> PreflightResult:
    """Run all preflight checks.

    Validates:
    - Required tools are present
    - Framework is installed as editable from a valid git clone
    - Current directory is inside a Git working tree
    - Current directory is the repository root
    - Repository is not bare
    - Git index has no staged changes
    - The agent tool's config directory doesn't exist (unless --force)
    """
    spec = get_tool_spec(agent_tool)
    config_dirname = spec.config_dirname
    missing_tools = check_required_tools()
    if missing_tools:
        return PreflightResult(
            success=False,
            error=f"Missing required tools: {', '.join(missing_tools)}",
            remediation=f"Install missing tools: {' '.join(missing_tools)}",
            missing_tools=missing_tools,
        )

    if not _detect_framework_repo_path():
        return PreflightResult(
            success=False,
            error="Framework repository not found or invalid.",
            remediation=(
                "Install the framework as an editable package from a git clone:\n"
                "  pipx install -e <path-to-framework-git-clone>\n"
                "Clone the framework repository first, then install it with pipx."
            ),
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
        )

    if config_directory_exists(repo_root, agent_tool):
        if not force:
            return PreflightResult(
                success=False,
                error=f"{config_dirname}/ already exists",
                remediation=(
                    "Use --force to backup and regenerate, or remove it manually"
                ),
            )

    return PreflightResult(success=True)
