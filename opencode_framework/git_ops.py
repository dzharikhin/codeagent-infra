"""Git operations: repository queries, worktree, and branch management."""

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional


@dataclass
class WorktreeResult:
    """Result of worktree creation."""

    success: bool
    path: Optional[Path] = None
    error: Optional[str] = None


def run_git_command(
    args: List[str],
    cwd: Optional[Path] = None,
    check: bool = False,
) -> subprocess.CompletedProcess:
    """Run a git command, returning a CompletedProcess.

    Failed commands and timeouts are converted into non-zero return
    codes instead of raising, unless ``check`` is set (in which case a
    non-zero exit raises ``subprocess.CalledProcessError`` only for the
    converted timeout-free cases handled below).
    """
    try:
        return subprocess.run(
            ["git"] + args,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=60,
            check=check,
        )
    except subprocess.CalledProcessError as e:
        return subprocess.CompletedProcess(
            args=e.args,
            returncode=e.returncode,
            stdout=e.stdout or "",
            stderr=e.stderr or "",
        )
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(
            args=["git"] + args,
            returncode=-1,
            stdout="",
            stderr="Git command timed out",
        )
    except FileNotFoundError as e:
        return subprocess.CompletedProcess(
            args=["git"] + args,
            returncode=-1,
            stdout="",
            stderr=str(e),
        )


def branch_exists(branch_name: str, cwd: Optional[Path] = None) -> bool:
    """Check if a branch exists locally."""
    result = run_git_command(
        ["rev-parse", "--verify", f"refs/heads/{branch_name}"],
        cwd=cwd,
    )
    return result.returncode == 0


def get_current_branch(cwd: Optional[Path] = None) -> Optional[str]:
    """Get the current branch name."""
    result = run_git_command(
        ["branch", "--show-current"],
        cwd=cwd,
    )
    if result.returncode == 0 and result.stdout.strip():
        return result.stdout.strip()
    return None


def is_inside_git_tree(path: Path) -> bool:
    """Check if path is inside a Git working tree."""
    result = run_git_command(["rev-parse", "--is-inside-work-tree"], cwd=path)
    return result.returncode == 0


def is_bare_repository(path: Path) -> bool:
    """Check if the repository is bare."""
    result = run_git_command(["rev-parse", "--is-bare-repository"], cwd=path)
    return result.returncode == 0 and result.stdout.strip().lower() == "true"


def get_repo_root(path: Path) -> Optional[Path]:
    """Get the repository root directory."""
    result = run_git_command(["rev-parse", "--show-toplevel"], cwd=path)
    if result.returncode == 0 and result.stdout.strip():
        return Path(result.stdout.strip())
    return None


def has_staged_changes(path: Path) -> bool:
    """Check if the Git index has staged changes."""
    result = run_git_command(["diff", "--cached", "--quiet"], cwd=path)
    return result.returncode != 0


def create_worktree(
    worktree_path: Path,
    branch_name: str,
    cwd: Optional[Path] = None,
) -> WorktreeResult:
    """Create a linked worktree.

    If branch doesn't exist, creates it as an orphan branch.
    """
    if branch_exists(branch_name, cwd=cwd):
        result = run_git_command(
            ["worktree", "add", str(worktree_path), branch_name],
            cwd=cwd,
        )
    else:
        result = run_git_command(
            ["worktree", "add", "--orphan", "-b", branch_name, str(worktree_path)],
            cwd=cwd,
        )

    if result.returncode != 0:
        return WorktreeResult(
            success=False,
            error=result.stderr.strip() or "Failed to create worktree",
        )

    return WorktreeResult(
        success=True,
        path=worktree_path,
    )


def remove_worktree(worktree_path: Path, cwd: Optional[Path] = None) -> bool:
    """Remove a worktree."""
    result = run_git_command(
        ["worktree", "remove", str(worktree_path), "--force"],
        cwd=cwd,
    )
    return result.returncode == 0


def is_worktree(path: Path) -> bool:
    """Check if the given path is a worktree."""
    git_file = path / ".git"
    if git_file.is_file():
        return True
    return False


def make_initial_commit(
    message: str,
    cwd: Optional[Path] = None,
    allow_empty: bool = True,
) -> bool:
    """Create an initial commit.

    Returns True on success.
    """
    args = ["commit", "-m", message]
    if allow_empty:
        args.append("--allow-empty")

    result = run_git_command(args, cwd=cwd)
    return result.returncode == 0


def setup_config_worktree(
    repo_root: Path,
    branch_name: str,
    config_dir: Path,
) -> WorktreeResult:
    """Set up the config directory as a linked git worktree.

    This function:
    1. Creates the worktree at config_dir (e.g. .opencode/ or .qwen/)
    2. Uses an orphan branch if it doesn't exist
    3. Creates an initial empty commit

    Returns the result of the worktree creation.
    """
    existing_branch = branch_exists(branch_name, cwd=repo_root)

    result = create_worktree(config_dir, branch_name, cwd=repo_root)

    if not result.success:
        return result

    if not existing_branch:
        success = make_initial_commit(
            message="Initial OpenCode framework configuration",
            cwd=config_dir,
            allow_empty=True,
        )
        if not success:
            remove_worktree(config_dir, cwd=repo_root)
            return WorktreeResult(
                success=False,
                error="Failed to create initial commit",
            )

    return result
