"""Tests for runtime helpers."""

import os
from pathlib import Path

import pytest

from opencode_framework.runtime import (
    validate_runtime_context,
    load_and_expand_env,
    build_devcontainer_env,
    _expand_value,
)


class TestValidateRuntimeContext:
    """Tests for runtime context validation."""

    def test_fails_outside_git_tree(self, tmp_path: Path):
        """Should fail when not inside a Git tree."""
        valid, error = validate_runtime_context(tmp_path)
        assert valid is False
        assert "not inside a Git working tree" in error

    def test_fails_not_at_repo_root(self, tmp_path: Path):
        """Should fail when not at repo root."""
        import subprocess
        
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
        
        subdir = tmp_path / "subdir"
        subdir.mkdir()
        
        valid, error = validate_runtime_context(subdir)
        assert valid is False
        assert "not the repository root" in error

    def test_fails_missing_opencode_dir(self, tmp_path: Path):
        """Should fail when .opencode/ does not exist."""
        import subprocess
        
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
        
        valid, error = validate_runtime_context(tmp_path)
        assert valid is False
        assert ".opencode/" in error

    def test_fails_missing_devcontainer_json(self, tmp_path: Path):
        """Should fail when devcontainer.json does not exist."""
        import subprocess
        
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
        
        valid, error = validate_runtime_context(tmp_path)
        assert valid is False
        assert "devcontainer.json" in error

    def test_fails_missing_env_file(self, tmp_path: Path):
        """Should fail when .env does not exist."""
        import subprocess
        
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
        
        opencode_dir = tmp_path / ".opencode"
        opencode_dir.mkdir()
        (opencode_dir / "devcontainer.json").write_text("{}")
        
        valid, error = validate_runtime_context(tmp_path)
        assert valid is False
        assert ".env" in error

    def test_fails_missing_framework_path_in_env(self, tmp_path: Path):
        """Should fail when OCF_LOCAL_FRAMEWORK_PATH is not set in .env."""
        import subprocess
        
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
        
        opencode_dir = tmp_path / ".opencode"
        opencode_dir.mkdir()
        (opencode_dir / "devcontainer.json").write_text("{}")
        (opencode_dir / ".env").write_text("REMOTE_USER=root\n")
        
        valid, error = validate_runtime_context(tmp_path)
        assert valid is False
        assert "OCF_LOCAL_FRAMEWORK_PATH" in error

    def test_fails_framework_path_not_exists(self, tmp_path: Path):
        """Should fail when framework path in .env does not exist."""
        import subprocess
        
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
        
        opencode_dir = tmp_path / ".opencode"
        opencode_dir.mkdir()
        (opencode_dir / "devcontainer.json").write_text("{}")
        (opencode_dir / ".env").write_text(
            "REMOTE_USER=root\n"
            "OCF_LOCAL_FRAMEWORK_PATH=/nonexistent/path/to/framework\n"
        )
        
        valid, error = validate_runtime_context(tmp_path)
        assert valid is False
        assert "Framework repository no longer exists" in error

    def test_fails_framework_path_invalid(self, tmp_path: Path):
        """Should fail when framework path exists but is not a valid framework repo."""
        import subprocess
        
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
        
        invalid_framework = tmp_path / "invalid-framework"
        invalid_framework.mkdir()
        (invalid_framework / ".git").mkdir()
        
        opencode_dir = tmp_path / ".opencode"
        opencode_dir.mkdir()
        (opencode_dir / "devcontainer.json").write_text("{}")
        (opencode_dir / ".env").write_text(
            f"REMOTE_USER=root\n"
            f"OCF_LOCAL_FRAMEWORK_PATH={invalid_framework}\n"
        )
        
        valid, error = validate_runtime_context(tmp_path)
        assert valid is False
        assert "Framework repository is invalid" in error

    def test_succeeds_with_valid_framework_repo(self, tmp_path: Path):
        """Should succeed when all requirements are met including valid framework repo."""
        import subprocess
        
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
        
        framework_repo = tmp_path / "framework"
        framework_repo.mkdir()
        (framework_repo / ".git").mkdir()
        (framework_repo / "framework-nuts-and-bolts").mkdir()
        (framework_repo / "framework-nuts-and-bolts" / "stub-auth.json").write_text("{}")
        (framework_repo / "framework-config").mkdir()
        
        opencode_dir = tmp_path / ".opencode"
        opencode_dir.mkdir()
        (opencode_dir / "devcontainer.json").write_text("{}")
        (opencode_dir / ".env").write_text(
            f"REMOTE_USER=root\n"
            f"OCF_LOCAL_FRAMEWORK_PATH={framework_repo}\n"
        )
        
        valid, error = validate_runtime_context(tmp_path)
        assert valid is True
        assert error == ""


class TestLoadAndExpandEnv:
    """Tests for .env loading and expansion."""

    def test_loads_simple_key_value(self, tmp_path: Path):
        """Should load simple KEY=VALUE pairs."""
        env_path = tmp_path / ".env"
        env_path.write_text("REMOTE_USER=root\nXDG_CONFIG_HOME=/home/root/.config\n")
        
        result = load_and_expand_env(env_path)
        
        assert result["REMOTE_USER"] == "root"
        assert result["XDG_CONFIG_HOME"] == "/home/root/.config"

    def test_ignores_comments_and_blanks(self, tmp_path: Path):
        """Should ignore comments and blank lines."""
        env_path = tmp_path / ".env"
        env_path.write_text("# Comment\n\nREMOTE_USER=root\n# Another comment\n")
        
        result = load_and_expand_env(env_path)
        
        assert result == {"REMOTE_USER": "root"}

    def test_expands_var_reference(self, tmp_path: Path):
        """Should expand ${VAR} references."""
        env_path = tmp_path / ".env"
        env_path.write_text("REMOTE_USER=root\nXDG_CONFIG_HOME=/home/${REMOTE_USER}/.config\n")
        
        result = load_and_expand_env(env_path)
        
        assert result["REMOTE_USER"] == "root"
        assert result["XDG_CONFIG_HOME"] == "/home/root/.config"

    def test_expands_var_with_default(self, tmp_path: Path):
        """Should expand ${VAR:-default} syntax."""
        env_path = tmp_path / ".env"
        env_path.write_text("REMOTE_USER=root\nXDG_CONFIG_HOME=/home/${REMOTE_USER:-nobody}/.config\n")
        
        result = load_and_expand_env(env_path)
        
        assert result["XDG_CONFIG_HOME"] == "/home/root/.config"

    def test_uses_default_when_var_not_set(self, tmp_path: Path):
        """Should use default value when variable is not set."""
        env_path = tmp_path / ".env"
        env_path.write_text("XDG_CONFIG_HOME=/home/${REMOTE_USER:-nobody}/.config\n")
        
        result = load_and_expand_env(env_path)
        
        assert result["XDG_CONFIG_HOME"] == "/home/nobody/.config"

    def test_nested_expansion(self, tmp_path: Path):
        """Should handle nested variable references."""
        env_path = tmp_path / ".env"
        env_path.write_text(
            "REMOTE_USER=root\n"
            "XDG_CONFIG_HOME=/home/${REMOTE_USER}/.config\n"
            "OPENCODE_CONFIG=${XDG_CONFIG_HOME}/opencode/config.json\n"
        )
        
        result = load_and_expand_env(env_path)
        
        assert result["OPENCODE_CONFIG"] == "/home/root/.config/opencode/config.json"

    def test_returns_empty_dict_for_missing_file(self, tmp_path: Path):
        """Should return empty dict if file doesn't exist."""
        env_path = tmp_path / ".nonexistent"
        
        result = load_and_expand_env(env_path)
        
        assert result == {}


class TestExpandValue:
    """Tests for the _expand_value helper."""

    def test_no_expansion(self):
        """Should return value unchanged if no variables."""
        result = _expand_value("simple value", {})
        assert result == "simple value"

    def test_simple_expansion(self):
        """Should expand ${VAR}."""
        result = _expand_value("prefix_${VAR}_suffix", {"VAR": "value"})
        assert result == "prefix_value_suffix"

    def test_default_expansion(self):
        """Should use default when variable not set."""
        result = _expand_value("${VAR:-default}", {})
        assert result == "default"

    def test_default_ignored_when_set(self):
        """Should use actual value when variable is set."""
        result = _expand_value("${VAR:-default}", {"VAR": "actual"})
        assert result == "actual"

    def test_multiple_variables(self):
        """Should expand multiple variables."""
        result = _expand_value("${A}/${B}", {"A": "foo", "B": "bar"})
        assert result == "foo/bar"


class TestBuildDevcontainerEnv:
    """Tests for building devcontainer subprocess environment."""

    def test_merges_base_env(self):
        """Should merge base env with current environment."""
        base_env = {"REMOTE_USER": "root", "XDG_CONFIG_HOME": "/home/root/.config"}
        
        result = build_devcontainer_env(base_env, "rootless")
        
        assert result["REMOTE_USER"] == "root"
        assert result["XDG_CONFIG_HOME"] == "/home/root/.config"

    def test_sets_docker_context(self):
        """Should set DOCKER_CONTEXT."""
        result = build_devcontainer_env({}, "rootless")
        assert result["DOCKER_CONTEXT"] == "rootless"

    def test_overrides_docker_context(self):
        """Should allow overriding DOCKER_CONTEXT."""
        result = build_devcontainer_env({}, "my-custom-context")
        assert result["DOCKER_CONTEXT"] == "my-custom-context"

    def test_base_env_overrides_process_env(self):
        """Base env values should override process env."""
        old_value = os.environ.get("TEST_VAR")
        try:
            os.environ["TEST_VAR"] = "process_value"
            result = build_devcontainer_env({"TEST_VAR": "base_value"}, "rootless")
            assert result["TEST_VAR"] == "base_value"
        finally:
            if old_value is None:
                os.environ.pop("TEST_VAR", None)
            else:
                os.environ["TEST_VAR"] = old_value

    def test_inherits_process_env(self):
        """Should inherit current process environment."""
        old_value = os.environ.get("PATH")
        result = build_devcontainer_env({}, "rootless")
        assert "PATH" in result
        if old_value:
            assert result["PATH"] == old_value
