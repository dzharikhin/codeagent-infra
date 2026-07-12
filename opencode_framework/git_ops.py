"""Git operations for worktree and branch management."""

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional


@dataclass
class GitBranchInfo:
    """Information about a Git branch."""

    name: str
    exists: bool
    is_orphan: bool = False


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
    """Run a git command."""
    try:
        result = subprocess.run(
            ["git"] + args,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=60,
            check=check,
        )
        return result
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


def create_orphan_branch(
    branch_name: str,
    cwd: Optional[Path] = None,
) -> bool:
    """Create an orphan branch with no commit history.

    Returns True on success.
    """
    result = run_git_command(
        ["checkout", "--orphan", branch_name],
        cwd=cwd,
    )
    if result.returncode != 0:
        return False

    result = run_git_command(
        ["reset", "--hard"],
        cwd=cwd,
    )
    return result.returncode == 0


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


def list_worktrees(cwd: Optional[Path] = None) -> List[Path]:
    """List all worktree paths."""
    result = run_git_command(
        ["worktree", "list", "--porcelain"],
        cwd=cwd,
    )

    worktrees = []
    if result.returncode == 0:
        for line in result.stdout.splitlines():
            if line.startswith("worktree "):
                worktree_path = Path(line.split(" ", 1)[1])
                worktrees.append(worktree_path)

    return worktrees


def is_worktree(path: Path) -> bool:
    """Check if the given path is a worktree."""
    git_file = path / ".git"
    if git_file.is_file():
        return True
    return False


def get_worktree_gitdir(worktree_path: Path) -> Optional[Path]:
    """Get the .git directory for a worktree."""
    git_file = worktree_path / ".git"
    if git_file.is_file():
        content = git_file.read_text().strip()
        if content.startswith("gitdir: "):
            gitdir = content[8:]
            return worktree_path / gitdir
    return None


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


def add_all_files(cwd: Optional[Path] = None) -> bool:
    """Stage all files in the working directory."""
    result = run_git_command(["add", "."], cwd=cwd)
    return result.returncode == 0


def setup_opencode_worktree(
    repo_root: Path,
    branch_name: str,
    opencode_dir: Path,
) -> WorktreeResult:
    """Set up the .opencode directory as a worktree.

    This function:
    1. Creates the worktree at .opencode/
    2. Uses an orphan branch if it doesn't exist
    3. Creates an initial empty commit

    Returns the result of the worktree creation.
    """
    existing_branch = branch_exists(branch_name, cwd=repo_root)

    result = create_worktree(opencode_dir, branch_name, cwd=repo_root)

    if not result.success:
        return result

    if not existing_branch:
        success = make_initial_commit(
            message="Initial OpenCode framework configuration",
            cwd=opencode_dir,
            allow_empty=True,
        )
        if not success:
            remove_worktree(opencode_dir, cwd=repo_root)
            return WorktreeResult(
                success=False,
                error="Failed to create initial commit",
            )

    return result
