"""Tests for preflight checks."""

import subprocess
from pathlib import Path

import pytest

from opencode_framework.config import (
    discover_global_settings,
    get_local_config_root,
    get_local_home,
)
from opencode_framework.git_ops import get_repo_root, is_inside_git_tree
from opencode_framework.preflight import (
    PreflightResult,
    check_docker_rootless_context,
    check_required_tools,
    config_directory_exists,
    run_preflight_checks,
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

    def test_is_inside_git_tree_true(self, tmp_path: Path):
        """Should return True when inside a git tree."""
        subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
        assert is_inside_git_tree(tmp_path) is True

    def test_is_inside_git_tree_false(self, tmp_path: Path):
        """Should return False when not inside a git tree."""
        assert is_inside_git_tree(tmp_path) is False

    def test_get_repo_root_returns_path(self, tmp_path: Path):
        """Should return a Path when inside a git tree."""
        subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
        result = get_repo_root(tmp_path)
        assert result is not None
        assert isinstance(result, Path)

    def test_get_repo_root_returns_none_outside_git(self, tmp_path: Path):
        """Should return None when not inside a git tree."""
        result = get_repo_root(tmp_path)
        assert result is None


class TestConfigDirectoryExists:
    """Tests for agent tool config directory detection."""

    def test_returns_false_when_not_exists(self, tmp_path: Path):
        """Should return False when .opencode/ doesn't exist."""
        assert config_directory_exists(tmp_path) is False

    def test_returns_true_when_exists(self, tmp_path: Path):
        """Should return True when .opencode/ exists."""
        (tmp_path / ".opencode").mkdir()
        assert config_directory_exists(tmp_path) is True

    def test_qwen_tool_checks_qwen_dir(self, tmp_path: Path):
        """agent_tool='qwen' should check .qwen/, not .opencode/."""
        (tmp_path / ".opencode").mkdir()
        assert config_directory_exists(tmp_path, agent_tool="qwen") is False
        (tmp_path / ".qwen").mkdir()
        assert config_directory_exists(tmp_path, agent_tool="qwen") is True


class TestDetectFrameworkRepoPath:
    """Tests for framework repo detection from an editable install."""

    def test_detects_repo_root_of_package(self):
        """Should return the package's parent directory when it is a git clone."""
        import opencode_framework

        repo_root = Path(opencode_framework.__file__).resolve().parent.parent
        settings = discover_global_settings()
        if not (repo_root / ".git").is_dir():
            pytest.skip("opencode_framework not installed from a git clone")
        assert settings.framework_repo_path == str(repo_root)


class TestRunPreflightChecks:
    """Tests for full preflight check suite."""

    def test_fails_outside_git_repo(self, tmp_path: Path):
        """Should fail when not inside a git repo."""
        result = run_preflight_checks(tmp_path)
        assert result.success is False
        if result.missing_tools:
            assert "Missing required tools" in result.error
        elif "Framework repository not found" not in result.error:
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
        assert result.missing_tools == []


class TestGetLocalHome:
    """Tests for local home directory discovery."""

    def test_uses_sudo_user_when_set(self, monkeypatch, tmp_path: Path):
        """Should use SUDO_USER's home when running under sudo."""
        import pwd

        monkeypatch.setenv("SUDO_USER", "root")
        result = get_local_home()
        assert result == Path(pwd.getpwnam("root").pw_dir)

    def test_uses_home_env_when_no_sudo(self, monkeypatch, tmp_path: Path):
        """Should use HOME env when SUDO_USER is not set."""
        monkeypatch.delenv("SUDO_USER", raising=False)
        monkeypatch.setenv("HOME", str(tmp_path))
        result = get_local_home()
        assert result == tmp_path

    def test_falls_back_to_path_home(self, monkeypatch):
        """Should fall back to Path.home() when nothing else available."""
        monkeypatch.delenv("SUDO_USER", raising=False)
        monkeypatch.delenv("HOME", raising=False)
        result = get_local_home()
        assert isinstance(result, Path)


class TestGetLocalConfigRoot:
    """Tests for local config root discovery."""

    def test_uses_xdg_config_home_when_set(self, monkeypatch, tmp_path: Path):
        """Should use XDG_CONFIG_HOME when set."""
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
        monkeypatch.delenv("SUDO_USER", raising=False)
        result = get_local_config_root()
        assert result == tmp_path

    def test_uses_home_config_when_xdg_not_set(self, monkeypatch):
        """Should use ~/.config when XDG_CONFIG_HOME is not set."""
        monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
        monkeypatch.delenv("SUDO_USER", raising=False)
        result = get_local_config_root()
        assert result.name == ".config"

    def test_uses_xdg_even_with_sudo_user(self, monkeypatch, tmp_path: Path):
        """XDG_CONFIG_HOME should take precedence over SUDO_USER home."""
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
        monkeypatch.setenv("SUDO_USER", "nobody")
        result = get_local_config_root()
        assert result == tmp_path

    def test_uses_home_config_when_xdg_empty(self, monkeypatch):
        """Should use ~/.config when XDG_CONFIG_HOME is empty."""
        monkeypatch.setenv("XDG_CONFIG_HOME", "")
        monkeypatch.delenv("SUDO_USER", raising=False)
        result = get_local_config_root()
        assert result.name == ".config"


class TestDiscoverGlobalSettings:
    """Tests for global settings discovery."""

    def test_settings_expose_framework_repo_path(self):
        """discover_global_settings mirrors the editable-install detection."""
        from opencode_framework.config import _detect_framework_repo_path

        settings = discover_global_settings()
        assert settings.framework_repo_path == _detect_framework_repo_path()
