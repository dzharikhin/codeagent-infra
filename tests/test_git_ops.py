"""Tests for Git operations."""

import shutil
import subprocess
from pathlib import Path

import pytest

from opencode_framework.git_ops import (
    branch_exists,
    create_orphan_branch,
    create_worktree,
    get_current_branch,
    is_worktree,
    list_worktrees,
    make_initial_commit,
    remove_worktree,
    setup_opencode_worktree,
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

    def test_list_worktrees(self, git_repo: Path):
        """list_worktrees returns all worktrees."""
        worktree_path = git_repo / ".opencode"
        create_worktree(worktree_path, "test-branch", cwd=git_repo)
        
        worktrees = list_worktrees(cwd=git_repo)
        
        assert len(worktrees) == 2
        assert git_repo in worktrees
        assert worktree_path in worktrees


class TestSetupOpencodeWorktree:
    """Tests for setup_opencode_worktree function."""

    def test_setup_creates_worktree(self, git_repo: Path):
        """setup_opencode_worktree creates a worktree."""
        opencode_dir = git_repo / ".opencode"
        branch_name = "codeagent-test"
        
        result = setup_opencode_worktree(
            repo_root=git_repo,
            branch_name=branch_name,
            opencode_dir=opencode_dir,
        )
        
        assert result.success
        assert opencode_dir.exists()
        assert branch_exists(branch_name, cwd=git_repo)
        assert is_worktree(opencode_dir)

    def test_setup_with_existing_branch(self, git_repo: Path):
        """setup_opencode_worktree reuses existing branch."""
        opencode_dir = git_repo / ".opencode"
        branch_name = "codeagent-test"
        
        result1 = setup_opencode_worktree(
            repo_root=git_repo,
            branch_name=branch_name,
            opencode_dir=opencode_dir,
        )
        assert result1.success
        
        remove_worktree(opencode_dir, cwd=git_repo)
        
        result2 = setup_opencode_worktree(
            repo_root=git_repo,
            branch_name=branch_name,
            opencode_dir=opencode_dir,
        )
        
        assert result2.success
        assert opencode_dir.exists()
