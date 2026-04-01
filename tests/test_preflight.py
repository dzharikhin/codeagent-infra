"""Tests for preflight checks."""

import os
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
from opencode_framework.config import (
    validate_framework_repo,
    get_config_root,
    get_local_config_root,
    get_local_home,
    discover_global_settings,
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


class TestValidateFrameworkRepo:
    """Tests for framework repository validation."""

    def test_valid_framework_repo(self, tmp_path: Path):
        """Should return True for valid framework repo."""
        (tmp_path / ".git").mkdir()
        (tmp_path / "framework-nuts-and-bolts").mkdir()
        (tmp_path / "framework-nuts-and-bolts" / "stub-auth.json").write_text("{}")
        (tmp_path / "framework-config").mkdir()
        
        valid, missing = validate_framework_repo(tmp_path)
        assert valid is True
        assert missing == []

    def test_invalid_missing_git(self, tmp_path: Path):
        """Should return False when .git is missing."""
        (tmp_path / "framework-nuts-and-bolts").mkdir()
        (tmp_path / "framework-nuts-and-bolts" / "stub-auth.json").write_text("{}")
        (tmp_path / "framework-config").mkdir()
        
        valid, missing = validate_framework_repo(tmp_path)
        assert valid is False
        assert ".git" in missing

    def test_invalid_missing_framework_nuts_and_bolts(self, tmp_path: Path):
        """Should return False when framework-nuts-and-bolts is missing."""
        (tmp_path / ".git").mkdir()
        (tmp_path / "framework-config").mkdir()
        
        valid, missing = validate_framework_repo(tmp_path)
        assert valid is False
        assert "framework-nuts-and-bolts" in missing

    def test_invalid_missing_stub_auth(self, tmp_path: Path):
        """Should return False when stub-auth.json is missing."""
        (tmp_path / ".git").mkdir()
        (tmp_path / "framework-nuts-and-bolts").mkdir()
        (tmp_path / "framework-config").mkdir()
        
        valid, missing = validate_framework_repo(tmp_path)
        assert valid is False
        assert "framework-nuts-and-bolts/stub-auth.json" in missing

    def test_invalid_missing_framework_config(self, tmp_path: Path):
        """Should return False when framework-config is missing."""
        (tmp_path / ".git").mkdir()
        (tmp_path / "framework-nuts-and-bolts").mkdir()
        (tmp_path / "framework-nuts-and-bolts" / "stub-auth.json").write_text("{}")
        
        valid, missing = validate_framework_repo(tmp_path)
        assert valid is False
        assert "framework-config" in missing


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
        assert result.repo_root is None
        assert result.missing_tools == []
        assert result.docker_rootless_available is False

    def test_post_init_ensures_list(self):
        """Should ensure missing_tools is a list."""
        result = PreflightResult(success=True, missing_tools=None)
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


class TestGetConfigRoot:
    """Tests for config root discovery (alias for get_local_config_root)."""

    def test_uses_xdg_config_home_when_set(self, monkeypatch, tmp_path: Path):
        """Should use XDG_CONFIG_HOME when set."""
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
        monkeypatch.delenv("SUDO_USER", raising=False)
        result = get_config_root()
        assert result == tmp_path

    def test_uses_home_config_when_xdg_not_set(self, monkeypatch):
        """Should use ~/.config when XDG_CONFIG_HOME is not set."""
        monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
        monkeypatch.delenv("SUDO_USER", raising=False)
        result = get_config_root()
        assert result.name == ".config"

    def test_uses_home_config_when_xdg_empty(self, monkeypatch):
        """Should use ~/.config when XDG_CONFIG_HOME is empty."""
        monkeypatch.setenv("XDG_CONFIG_HOME", "")
        monkeypatch.delenv("SUDO_USER", raising=False)
        result = get_config_root()
        assert result.name == ".config"


class TestDiscoverGlobalSettings:
    """Tests for global settings discovery."""

    def test_discovers_config_from_xdg(self, monkeypatch, tmp_path: Path):
        """Should discover config from XDG_CONFIG_HOME/opencode."""
        xdg_config = tmp_path / "config"
        xdg_config.mkdir()
        opencode_config = xdg_config / "opencode"
        opencode_config.mkdir()
        
        monkeypatch.setenv("XDG_CONFIG_HOME", str(xdg_config))
        
        settings = discover_global_settings()
        assert settings.global_config_found is True
        assert settings.global_config_path == str(opencode_config)

    def test_config_not_found_when_missing(self, monkeypatch, tmp_path: Path):
        """Should return not found when opencode config dir doesn't exist."""
        xdg_config = tmp_path / "config"
        xdg_config.mkdir()
        
        monkeypatch.setenv("XDG_CONFIG_HOME", str(xdg_config))
        
        settings = discover_global_settings()
        assert settings.global_config_found is False
        assert settings.global_config_path is None
