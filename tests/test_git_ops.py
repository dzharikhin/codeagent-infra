"""Tests for Git operations."""

import shutil
import subprocess
from pathlib import Path
from typing import List, Optional, Tuple

import pytest

from opencode_framework.git_ops import (
    branch_exists,
    create_worktree,
    get_current_branch,
    is_worktree,
    list_worktrees,
    make_initial_commit,
    remove_worktree,
    setup_config_worktree,
    uncommitted_changes,
)

pytestmark = pytest.mark.skipif(
    shutil.which("git") is None,
    reason="git not installed",
)


@pytest.fixture
def git_repo(tmp_path: Path) -> Path:
    """Create a temporary git repository."""
    repo = tmp_path / "test_repo"
    repo.mkdir()

    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=repo,
        check=True,
        capture_output=True,
    )

    (repo / "README.md").write_text("# Test Repo\n")
    subprocess.run(["git", "add", "."], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "Initial commit"],
        cwd=repo,
        check=True,
        capture_output=True,
    )

    return repo


class TestBranchOperations:
    """Tests for branch-related operations."""

    def test_branch_exists_false(self, git_repo: Path):
        """branch_exists returns False for non-existent branch."""
        assert not branch_exists("nonexistent-branch", cwd=git_repo)

    def test_branch_exists_true(self, git_repo: Path):
        """branch_exists returns True for existing branch."""
        branch = get_current_branch(git_repo)
        assert branch is not None
        assert branch_exists(branch, cwd=git_repo)

    def test_get_current_branch(self, git_repo: Path):
        """get_current_branch returns the current branch name."""
        branch = get_current_branch(git_repo)
        assert branch in ("main", "master")


class TestWorktreeOperations:
    """Tests for worktree operations."""

    def test_is_worktree_false(self, git_repo: Path):
        """is_worktree returns False for main repo."""
        assert not is_worktree(git_repo)

    def test_create_worktree_new_branch(self, git_repo: Path):
        """create_worktree creates a new worktree with a new orphan branch."""
        worktree_path = git_repo / ".opencode"
        branch_name = "test-branch"

        result = create_worktree(worktree_path, branch_name, cwd=git_repo)

        assert result.success
        assert result.path == worktree_path
        assert worktree_path.exists()
        assert is_worktree(worktree_path)

    def test_is_worktree_true(self, git_repo: Path):
        """is_worktree returns True for a worktree."""
        worktree_path = git_repo / ".opencode"
        create_worktree(worktree_path, "test-branch", cwd=git_repo)

        assert is_worktree(worktree_path)

    def test_remove_worktree(self, git_repo: Path):
        """remove_worktree removes a worktree."""
        worktree_path = git_repo / ".opencode"
        create_worktree(worktree_path, "test-branch", cwd=git_repo)

        assert remove_worktree(worktree_path, cwd=git_repo)
        assert not worktree_path.exists()


class TestListWorktrees:
    """Tests for list_worktrees."""

    def test_main_worktree_only(self, git_repo: Path):
        """list_worktrees returns the main worktree when no linked ones exist."""
        assert [p.resolve() for p in list_worktrees(git_repo)] == [git_repo.resolve()]

    def test_includes_linked_worktrees(self, git_repo: Path):
        """list_worktrees includes linked worktrees of the repository."""
        create_worktree(git_repo / ".opencode", "codeagent-opencode", cwd=git_repo)

        paths = {p.resolve() for p in list_worktrees(git_repo)}
        assert git_repo.resolve() in paths
        assert (git_repo / ".opencode").resolve() in paths

    def test_failure_returns_empty(self, tmp_path: Path):
        """list_worktrees fails open outside a repository."""
        assert list_worktrees(tmp_path) == []


class TestUncommittedChanges:
    """Tests for uncommitted_changes."""

    def test_clean_repo(self, git_repo: Path):
        """uncommitted_changes is empty on a clean repository."""
        assert uncommitted_changes(git_repo) == []

    def test_modified_tracked_file(self, git_repo: Path):
        """Modifications to tracked files are listed."""
        (git_repo / "README.md").write_text("# Changed\n")

        changes = uncommitted_changes(git_repo)

        assert len(changes) == 1
        assert "README.md" in changes[0]

    def test_untracked_file(self, git_repo: Path):
        """Untracked files are listed."""
        (git_repo / "notes.txt").write_text("hello\n")

        changes = uncommitted_changes(git_repo)

        assert len(changes) == 1
        assert "notes.txt" in changes[0]

    def test_ignored_path_excluded(self, git_repo: Path):
        """Ignored paths (e.g. runtime_data/) stay out of the listing."""
        (git_repo / ".gitignore").write_text("runtime_data/\n")
        (git_repo / "runtime_data").mkdir()
        (git_repo / "runtime_data" / "cache.bin").write_text("x")

        changes = uncommitted_changes(git_repo)

        assert all("runtime_data" not in line for line in changes)

    def test_inside_linked_worktree(self, git_repo: Path):
        """uncommitted_changes works inside a linked config worktree."""
        worktree = git_repo / ".opencode"
        create_worktree(worktree, "codeagent-dirty", cwd=git_repo)
        (worktree / "settings.json").write_text("{}\n")

        changes = uncommitted_changes(worktree)

        assert len(changes) == 1
        assert "settings.json" in changes[0]

    def test_failure_returns_empty(self, tmp_path: Path):
        """uncommitted_changes fails open outside a repository."""
        assert uncommitted_changes(tmp_path) == []


class TestMakeInitialCommit:
    """Tests for make_initial_commit."""

    def test_uses_bootstrap_flags(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """Bootstrap commit bypasses GPG signing and hooks."""
        captured: List[List[str]] = []

        def fake_run_git_command(
            args: List[str],
            cwd: Optional[Path] = None,
            check: bool = False,
        ) -> subprocess.CompletedProcess:
            captured.append(args)
            return subprocess.CompletedProcess(
                args=["git"] + args, returncode=0, stdout="", stderr=""
            )

        monkeypatch.setattr(
            "opencode_framework.git_ops.run_git_command", fake_run_git_command
        )

        success, stderr = make_initial_commit("Initial config", cwd=tmp_path)

        assert success
        assert stderr == ""
        args = captured[0]
        assert args[:2] == ["-c", "commit.gpgsign=false"]
        assert "commit" in args
        assert "-m" in args
        assert "--no-verify" in args
        assert "--allow-empty" in args

    def test_failure_propagates_stderr(
        self, git_repo: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """setup_config_worktree surfaces git stderr on bootstrap commit failure."""

        def fake_make_initial_commit(
            message: str,
            cwd: Optional[Path] = None,
            allow_empty: bool = True,
        ) -> Tuple[bool, str]:
            return False, "fatal: unable to auto-detect email address"

        monkeypatch.setattr(
            "opencode_framework.git_ops.make_initial_commit", fake_make_initial_commit
        )

        opencode_dir = git_repo / ".opencode"
        result = setup_config_worktree(
            repo_root=git_repo,
            branch_name="codeagent-fail",
            config_dir=opencode_dir,
        )

        assert not result.success
        assert result.error is not None
        assert "Failed to create initial commit" in result.error
        assert "fatal: unable to auto-detect email address" in result.error
        assert not opencode_dir.exists()

    def test_failure_without_stderr(
        self, git_repo: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """setup_config_worktree falls back to a plain message when stderr is empty."""

        def fake_make_initial_commit(
            message: str,
            cwd: Optional[Path] = None,
            allow_empty: bool = True,
        ) -> Tuple[bool, str]:
            return False, ""

        monkeypatch.setattr(
            "opencode_framework.git_ops.make_initial_commit", fake_make_initial_commit
        )

        opencode_dir = git_repo / ".opencode"
        result = setup_config_worktree(
            repo_root=git_repo,
            branch_name="codeagent-fail",
            config_dir=opencode_dir,
        )

        assert not result.success
        assert result.error == "Failed to create initial commit"


class TestSetupConfigWorktree:
    """Tests for setup_config_worktree function."""

    def test_setup_creates_worktree(self, git_repo: Path):
        """setup_config_worktree creates a worktree."""
        opencode_dir = git_repo / ".opencode"
        branch_name = "codeagent-test"

        result = setup_config_worktree(
            repo_root=git_repo,
            branch_name=branch_name,
            config_dir=opencode_dir,
        )

        assert result.success
        assert opencode_dir.exists()
        assert branch_exists(branch_name, cwd=git_repo)
        assert is_worktree(opencode_dir)

    def test_setup_with_existing_branch(self, git_repo: Path):
        """setup_config_worktree reuses existing branch."""
        opencode_dir = git_repo / ".opencode"
        branch_name = "codeagent-test"

        result1 = setup_config_worktree(
            repo_root=git_repo,
            branch_name=branch_name,
            config_dir=opencode_dir,
        )
        assert result1.success

        remove_worktree(opencode_dir, cwd=git_repo)

        result2 = setup_config_worktree(
            repo_root=git_repo,
            branch_name=branch_name,
            config_dir=opencode_dir,
        )

        assert result2.success
        assert opencode_dir.exists()
