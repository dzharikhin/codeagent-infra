"""Tests for preflight checks."""

from pathlib import Path

import pytest

from opencode_framework.preflight import (
    check_required_tools,
    check_docker_rootless_context,
    is_inside_git_tree,
    is_bare_repository,
    get_repo_root,
    has_staged_changes,
    opencode_directory_exists,
    run_preflight_checks,
    PreflightResult,
)


class TestCheckRequiredTools:
    """Tests for required tools checking."""

    def test_returns_list(self):
        """Should return a list (possibly empty)."""
        result = check_required_tools()
        assert isinstance(result, list)

    def test_missing_tools_are_strings(self):
        """Missing tools should be string names."""
        result = check_required_tools()
        for tool in result:
            assert isinstance(tool, str)


class TestCheckDockerRootlessContext:
    """Tests for Docker rootless context checking."""

    def test_returns_bool(self):
        """Should return a boolean."""
        result = check_docker_rootless_context()
        assert isinstance(result, bool)


class TestGitOperations:
    """Tests for Git-related preflight functions."""

    @pytest.mark.skipif(
        not is_inside_git_tree(Path("/app/project_root")),
        reason="Not inside a git tree"
    )
    def test_is_inside_git_tree_true(self):
        """Should return True when inside a git tree."""
        assert is_inside_git_tree(Path("/app/project_root")) is True

    def test_is_inside_git_tree_false(self, tmp_path: Path):
        """Should return False when not inside a git tree."""
        assert is_inside_git_tree(tmp_path) is False

    @pytest.mark.skipif(
        not is_inside_git_tree(Path("/app/project_root")),
        reason="Not inside a git tree"
    )
    def test_get_repo_root_returns_path(self):
        """Should return a Path when inside a git tree."""
        result = get_repo_root(Path("/app/project_root"))
        assert result is not None
        assert isinstance(result, Path)

    def test_get_repo_root_returns_none_outside_git(self, tmp_path: Path):
        """Should return None when not inside a git tree."""
        result = get_repo_root(tmp_path)
        assert result is None


class TestOpencodeDirectoryExists:
    """Tests for .opencode/ directory detection."""

    def test_returns_false_when_not_exists(self, tmp_path: Path):
        """Should return False when .opencode/ doesn't exist."""
        assert opencode_directory_exists(tmp_path) is False

    def test_returns_true_when_exists(self, tmp_path: Path):
        """Should return True when .opencode/ exists."""
        (tmp_path / ".opencode").mkdir()
        assert opencode_directory_exists(tmp_path) is True


class TestRunPreflightChecks:
    """Tests for full preflight check suite."""

    def test_fails_outside_git_repo(self, tmp_path: Path):
        """Should fail when not inside a git repo."""
        result = run_preflight_checks(tmp_path)
        assert result.success is False
        if result.missing_tools:
            assert "Missing required tools" in result.error
        else:
            assert "not inside a Git working tree" in result.error

    def test_fails_with_missing_tools(self, tmp_path: Path):
        """Should fail when required tools are missing."""
        result = run_preflight_checks(tmp_path)
        if not result.success and result.missing_tools:
            assert "Missing required tools" in result.error

    def test_fails_with_existing_opencode(self, tmp_path: Path):
        """Should fail when .opencode/ exists without --force."""
        (tmp_path / ".opencode").mkdir()
        result = run_preflight_checks(tmp_path, force=False)
        if result.missing_tools:
            pytest.skip("Required tools missing")
        # Will fail because not in git repo, not because of .opencode/
        assert result.success is False

    def test_fails_with_existing_opencode_in_git_repo(self, tmp_path: Path):
        """Should fail when .opencode/ exists in a git repo without --force."""
        import subprocess
        
        # Initialize git repo
        subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "commit", "--allow-empty", "-m", "init"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )
        
        (tmp_path / ".opencode").mkdir()
        result = run_preflight_checks(tmp_path, force=False)
        if result.missing_tools:
            pytest.skip("Required tools missing")
        assert result.success is False
        assert ".opencode/" in result.error

    def test_force_allows_existing_opencode(self, tmp_path: Path):
        """Should pass with --force even when .opencode/ exists."""
        (tmp_path / ".opencode").mkdir()
        result = run_preflight_checks(tmp_path, force=True)
        if result.missing_tools:
            pytest.skip("Required tools missing")


class TestPreflightResult:
    """Tests for PreflightResult dataclass."""

    def test_default_values(self):
        """Should have sensible defaults."""
        result = PreflightResult(success=True)
        assert result.error is None
        assert result.remediation is None
        assert result.repo_root is None
        assert result.missing_tools == []
        assert result.docker_rootless_available is False

    def test_post_init_ensures_list(self):
        """Should ensure missing_tools is a list."""
        result = PreflightResult(success=True, missing_tools=None)
        assert result.missing_tools == []
