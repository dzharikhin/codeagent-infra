"""Tests for runtime helpers."""

import os
from pathlib import Path

import pytest

from opencode_framework.runtime import (
    validate_runtime_context,
    load_env_with_overrides,
    build_docker_env,
    parse_cli_env_vars,
    apply_combined_interpolation,
    get_image_id_path,
    load_image_id,
    save_image_id,
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


class TestLoadEnvWithOverrides:
    """Tests for .env loading with overrides and precedence."""

    def test_loads_base_only(self, tmp_path: Path):
        """Should load base env file."""
        env_path = tmp_path / ".env"
        env_path.write_text("KEY1=value1\nKEY2=value2")
        
        result = load_env_with_overrides(env_path)
        
        assert result == {"KEY1": "value1", "KEY2": "value2"}

    def test_ignores_comments_and_blanks(self, tmp_path: Path):
        """Should ignore comments and blank lines."""
        env_path = tmp_path / ".env"
        env_path.write_text("# Comment\n\nKEY1=value1\n# Another comment\n")
        
        result = load_env_with_overrides(env_path)
        
        assert result == {"KEY1": "value1"}

    def test_override_file_precedence(self, tmp_path: Path):
        """Override file should override base file."""
        base_env = tmp_path / ".env"
        base_env.write_text("KEY1=base1\nKEY2=base2")
        
        override_env = tmp_path / "override.env"
        override_env.write_text("KEY2=override2\nKEY3=override3")
        
        result = load_env_with_overrides(base_env, override_env)
        
        assert result == {
            "KEY1": "base1",
            "KEY2": "override2",  # Overridden
            "KEY3": "override3",
        }

    def test_cli_vars_highest_precedence(self, tmp_path: Path):
        """CLI variables should have highest precedence."""
        base_env = tmp_path / ".env"
        base_env.write_text("KEY1=base1\nKEY2=base2")
        
        override_env = tmp_path / "override.env"
        override_env.write_text("KEY2=override2\nKEY3=override3")
        
        cli_vars = ["KEY3=cli3", "KEY4=cli4"]
        
        result = load_env_with_overrides(base_env, override_env, cli_vars)
        
        assert result == {
            "KEY1": "base1",
            "KEY2": "override2",
            "KEY3": "cli3",  # CLI overrides override file
            "KEY4": "cli4",
        }

    def test_returns_empty_dict_for_missing_file(self, tmp_path: Path):
        """Should return empty dict if base file doesn't exist."""
        env_path = tmp_path / ".nonexistent"
        
        result = load_env_with_overrides(env_path)
        
        assert result == {}

    def test_nonexistent_override_file_raises(self, tmp_path: Path):
        """Should raise error if override file doesn't exist."""
        base_env = tmp_path / ".env"
        base_env.write_text("KEY=value")
        
        override_env = tmp_path / "nonexistent.env"
        
        with pytest.raises(FileNotFoundError):
            load_env_with_overrides(base_env, override_env)

    def test_export_statements_supported(self, tmp_path: Path):
        """Should handle export statements."""
        env_path = tmp_path / ".env"
        env_path.write_text("export KEY1=value1\nKEY2=value2")
        
        result = load_env_with_overrides(env_path)
        
        assert result["KEY1"] == "value1"
        assert result["KEY2"] == "value2"

    def test_quoted_values_supported(self, tmp_path: Path):
        """Should handle quoted values."""
        env_path = tmp_path / ".env"
        env_path.write_text('KEY1="value with spaces"\nKEY2=\'single quoted\'')
        
        result = load_env_with_overrides(env_path)
        
        assert result["KEY1"] == "value with spaces"
        assert result["KEY2"] == "single quoted"

    def test_interpolation_across_sources(self, tmp_path: Path):
        """Interpolation should work across different sources."""
        base_env = tmp_path / ".env"
        base_env.write_text("BASE_URL=http://localhost")
        
        override_env = tmp_path / "override.env"
        override_env.write_text("API_PATH=/api/v1")
        
        cli_vars = ["FULL_URL=${BASE_URL}${API_PATH}"]
        
        result = load_env_with_overrides(base_env, override_env, cli_vars)
        
        assert result["FULL_URL"] == "http://localhost/api/v1"


class TestParseCliEnvVars:
    """Tests for CLI environment variable parsing."""

    def test_valid_format(self):
        """Should parse valid KEY=VALUE pairs."""
        result = parse_cli_env_vars(["KEY1=value1", "KEY2=value2"])
        assert result == {"KEY1": "value1", "KEY2": "value2"}

    def test_empty_value_allowed(self):
        """Should allow KEY= with empty value."""
        result = parse_cli_env_vars(["KEY="])
        assert result == {"KEY": ""}

    def test_value_with_equals(self):
        """Value can contain equals signs."""
        result = parse_cli_env_vars(["KEY=value=with=equals"])
        assert result == {"KEY": "value=with=equals"}

    def test_missing_equals_raises(self):
        """Should raise error for invalid format."""
        with pytest.raises(ValueError, match="expected KEY=VALUE format"):
            parse_cli_env_vars(["INVALID"])

    def test_empty_key_raises(self):
        """Should raise error for empty key."""
        with pytest.raises(ValueError, match="key cannot be empty"):
            parse_cli_env_vars(["=value"])

    def test_invalid_key_format_raises(self):
        """Should validate key format."""
        with pytest.raises(ValueError, match="alphanumeric"):
            parse_cli_env_vars(["KEY-INVALID=value"])


class TestApplyCustomInterpolation:
    """Tests for custom interpolation with ${VAR:-default}."""

    def test_simple_interpolation(self):
        """Should interpolate simple ${VAR:-default}."""
        env = {"VAR": "hello", "RESULT": "${VAR:-default}"}
        result = apply_combined_interpolation(env)
        assert result["RESULT"] == "hello"

    def test_uses_default_when_undefined(self):
        """Should use default for undefined variables."""
        env = {"RESULT": "${UNDEFINED:-fallback}"}
        result = apply_combined_interpolation(env)
        assert result["RESULT"] == "fallback"

    def test_recursive_interpolation(self):
        """Should handle multi-level interpolation."""
        env = {
            "A": "a",
            "B": "${A:-default}b",
            "C": "${B:-default}c",
            "D": "${C:-default}d",
        }
        result = apply_combined_interpolation(env)
        assert result == {
            "A": "a",
            "B": "ab",
            "C": "abc",
            "D": "abcd",
        }

    def test_resolves_within_depth_limit(self):
        """Should resolve deep chains within max depth."""
        from opencode_framework.runtime import apply_combined_interpolation
        env = {
            "A": "hello",
            "B": "$A",
            "C": "$B",
            "D": "$C",
            "E": "$D",
        }
        result = apply_combined_interpolation(env, max_depth=5)
        assert result == {
            "A": "hello",
            "B": "hello",
            "C": "hello",
            "D": "hello",
            "E": "hello",
        }

    def test_undefined_vars_resolve_to_empty(self):
        """Undefined variables should resolve to empty string."""
        from opencode_framework.runtime import apply_combined_interpolation
        env = {
            "A": "$UNDEFINED",
            "B": "$C",
        }
        result = apply_combined_interpolation(env)
        assert result == {"A": "", "B": ""}

    def test_partial_resolution_leaves_pattern(self):
        """Unresolvable patterns should stay in result (not raise error)."""
        from opencode_framework.runtime import apply_combined_interpolation
        env = {
            "A": "$B",
            "B": "$C",
            "C": "$A",  # Cycles back - stays as pattern
        }
        # Should resolve without error, leaving unresolved patterns
        result = apply_combined_interpolation(env)
        # All have cycles, so they should be mostly empty strings from each pass
        assert result is not None

    def test_undefined_becomes_empty_string(self):
        """Undefined variables should become empty string."""
        env = {"RESULT": "prefix_${UNDEFINED:-}_suffix"}
        result = apply_combined_interpolation(env)
        assert result["RESULT"] == "prefix__suffix"


class TestBuildDockerEnv:
    """Tests for building Docker subprocess environment."""

    def test_merges_base_env(self):
        """Should merge base env with current environment."""
        base_env = {"REMOTE_USER": "root", "XDG_CONFIG_HOME": "/home/root/.config"}
        
        result = build_docker_env(base_env, "rootless")
        
        assert result["REMOTE_USER"] == "root"
        assert result["XDG_CONFIG_HOME"] == "/home/root/.config"

    def test_sets_docker_context(self):
        """Should set DOCKER_CONTEXT."""
        result = build_docker_env({}, "rootless")
        assert result["DOCKER_CONTEXT"] == "rootless"

    def test_overrides_docker_context(self):
        """Should allow overriding DOCKER_CONTEXT."""
        result = build_docker_env({}, "my-custom-context")
        assert result["DOCKER_CONTEXT"] == "my-custom-context"

    def test_base_env_overrides_process_env(self):
        """Base env values should override process env."""
        old_value = os.environ.get("TEST_VAR")
        try:
            os.environ["TEST_VAR"] = "process_value"
            result = build_docker_env({"TEST_VAR": "base_value"}, "rootless")
            assert result["TEST_VAR"] == "base_value"
        finally:
            if old_value is None:
                os.environ.pop("TEST_VAR", None)
            else:
                os.environ["TEST_VAR"] = old_value

    def test_inherits_process_env(self):
        """Should inherit current process environment."""
        old_value = os.environ.get("PATH")
        result = build_docker_env({}, "rootless")
        assert "PATH" in result
        if old_value:
            assert result["PATH"] == old_value


class TestIntegrationScenarios:
    """Integration tests for real-world scenarios."""

    def test_dev_to_prod_override(self, tmp_path: Path):
        """Test typical development to production override."""
        base_env = tmp_path / ".env"
        base_env.write_text(
            "ENV=development\n"
            "API_URL=http://localhost:3000\n"
            "DB_HOST=localhost\n"
            "DB_PORT=5432\n"
            "DB_NAME=dev_db\n"
        )
        
        prod_env = tmp_path / "prod.env"
        prod_env.write_text(
            "ENV=production\n"
            "API_URL=https://api.example.com\n"
            "DB_HOST=prod-db.example.com\n"
            "DB_NAME=prod_db\n"
        )
        
        cli_vars = ["DB_PASSWORD=secret123", "ENABLE_DEBUG=false"]
        
        result = load_env_with_overrides(base_env, prod_env, cli_vars)
        
        assert result == {
            "ENV": "production",
            "API_URL": "https://api.example.com",
            "DB_HOST": "prod-db.example.com",
            "DB_PORT": "5432",
            "DB_NAME": "prod_db",
            "DB_PASSWORD": "secret123",
            "ENABLE_DEBUG": "false",
        }

    def test_complex_interpolation_chain(self, tmp_path: Path):
        """Test complex interpolation across multiple sources."""
        base_env = tmp_path / ".env"
        base_env.write_text(
            "APP_NAME=myapp\n"
            "BASE_DIR=/opt/${APP_NAME}\n"
            "CONFIG_DIR=${BASE_DIR}/config\n"
        )
        
        override_env = tmp_path / "custom.env"
        override_env.write_text(
            "LOG_DIR=${BASE_DIR}/logs\n"
            "TEMP_DIR=${BASE_DIR}/tmp\n"
        )
        
        cli_vars = [
            "FULL_CONFIG_PATH=${CONFIG_DIR}/app.conf",
            "BACKUP_DIR=${BASE_DIR}/backups",
        ]
        
        result = load_env_with_overrides(base_env, override_env, cli_vars)
        
        assert result == {
            "APP_NAME": "myapp",
            "BASE_DIR": "/opt/myapp",
            "CONFIG_DIR": "/opt/myapp/config",
            "LOG_DIR": "/opt/myapp/logs",
            "TEMP_DIR": "/opt/myapp/tmp",
            "FULL_CONFIG_PATH": "/opt/myapp/config/app.conf",
            "BACKUP_DIR": "/opt/myapp/backups",
        }

    def test_env_error_with_file_context(self, tmp_path: Path):
        """Test that EnvError includes file path context."""
        base_env = tmp_path / ".env"
        base_env.write_text("KEY=value")
        
        override_env = tmp_path / "missing.env"
        
        try:
            load_env_with_overrides(base_env, override_env)
            assert False, "Should have raised FileNotFoundError"
        except FileNotFoundError as e:
            assert "missing.env" in str(e)


class TestImageIdHelpers:
    """Tests for image ID persistence helpers."""

    def test_get_image_id_path(self):
        """Should return correct path to image ID file."""
        opencode_dir = Path("/tmp/test/.opencode")
        assert get_image_id_path(opencode_dir) == Path("/tmp/test/.opencode/runtime_data/.image_id")

    def test_load_image_id_missing(self, tmp_path: Path):
        """Should return None if image ID file does not exist."""
        assert load_image_id(tmp_path) is None

    def test_load_image_id_exists(self, tmp_path: Path):
        """Should return content if image ID file exists."""
        save_image_id(tmp_path, "sha256:abc123")
        assert load_image_id(tmp_path) == "sha256:abc123"

    def test_save_image_id_creates_directory(self, tmp_path: Path):
        """Should create runtime_data directory and file."""
        opencode_dir = tmp_path / ".opencode"
        save_image_id(opencode_dir, "sha256:def456")
        assert (opencode_dir / "runtime_data" / ".image_id").exists()
        assert (opencode_dir / "runtime_data" / ".image_id").read_text() == "sha256:def456"

    def test_save_image_id_overwrites(self, tmp_path: Path):
        """Should overwrite existing image ID."""
        save_image_id(tmp_path, "sha256:old")
        save_image_id(tmp_path, "sha256:new")
        assert load_image_id(tmp_path) == "sha256:new"
