"""Tests for agent config layers: discovery, stubs, project layers."""

import json

from opencode_framework.agent.layers import (
    QWEN_PROJECT_SETTINGS_STUB,
    discover_global_layer,
    ensure_qwen_project_layer,
    expected_global_env_path,
)
from opencode_framework.agent.registry import OPENCODE_TOOL_SPEC, QWEN_TOOL_SPEC


class TestExpectedGlobalEnvPath:
    """Tests for per-tool global .env path resolution."""

    def test_opencode_resolves_under_config_root(self, tmp_path):
        path = expected_global_env_path(
            OPENCODE_TOOL_SPEC, config_root=tmp_path, home=tmp_path / "unused"
        )
        assert path == tmp_path / "opencode" / ".env"

    def test_qwen_resolves_under_home(self, tmp_path):
        path = expected_global_env_path(
            QWEN_TOOL_SPEC, config_root=tmp_path / "unused", home=tmp_path
        )
        assert path == tmp_path / ".qwen" / ".env"

    def test_opencode_default_follows_xdg_config_root(self, tmp_path, monkeypatch):
        monkeypatch.delenv("SUDO_USER", raising=False)
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg-config"))
        path = expected_global_env_path(OPENCODE_TOOL_SPEC)
        assert path == tmp_path / "xdg-config" / "opencode" / ".env"


class TestDiscoverGlobalLayerOpencode:
    """Tests for opencode global layer discovery."""

    def test_finds_config_dir_and_auth_file(self, tmp_path):
        config_root = tmp_path / "config"
        data_home = tmp_path / "data"
        (config_root / "opencode").mkdir(parents=True)
        auth = data_home / "opencode" / "auth.json"
        auth.parent.mkdir(parents=True)
        auth.write_text("{}")

        layer = discover_global_layer(
            OPENCODE_TOOL_SPEC,
            config_root=config_root,
            data_home=data_home,
        )
        assert layer.global_found is True
        assert layer.global_path == str(config_root / "opencode")
        assert layer.auth_found is True
        assert layer.auth_path == str(auth)

    def test_missing_paths_reported_not_found(self, tmp_path):
        layer = discover_global_layer(
            OPENCODE_TOOL_SPEC,
            config_root=tmp_path / "empty-config",
            data_home=tmp_path / "empty-data",
        )
        assert layer.global_found is False
        assert layer.global_path is None
        assert layer.auth_found is False
        assert layer.auth_path is None


class TestDiscoverGlobalLayerQwen:
    """Tests for qwen global layer discovery."""

    def test_finds_global_settings_file(self, tmp_path):
        home = tmp_path / "home"
        settings = home / ".qwen" / "settings.json"
        settings.parent.mkdir(parents=True)
        settings.write_text("{}")

        layer = discover_global_layer(QWEN_TOOL_SPEC, home=home)
        assert layer.global_found is True
        assert layer.global_path == str(settings)
        assert layer.auth_found is False
        assert layer.auth_path is None

    def test_missing_settings_file_not_found(self, tmp_path):
        layer = discover_global_layer(QWEN_TOOL_SPEC, home=tmp_path)
        assert layer.global_found is False
        assert layer.global_path is None

    def test_uses_host_home_by_default(self, tmp_path, monkeypatch):
        monkeypatch.delenv("SUDO_USER", raising=False)
        monkeypatch.setenv("HOME", str(tmp_path))
        settings = tmp_path / ".qwen" / "settings.json"
        settings.parent.mkdir(parents=True)
        settings.write_text("{}")
        layer = discover_global_layer(QWEN_TOOL_SPEC)
        assert layer.global_found is True
        assert layer.global_path == str(settings)


class TestStubFallback:
    """Tests for framework stub path resolution."""

    def test_opencode_stub_path_derived_from_framework_repo(self, tmp_path):
        layer = discover_global_layer(
            OPENCODE_TOOL_SPEC,
            config_root=tmp_path,
            framework_repo_path=str(tmp_path),
        )
        assert layer.stub_path == str(
            tmp_path / "framework-config" / "opencode" / "stubs" / "stub-auth.json"
        )

    def test_qwen_stub_path_derived_from_framework_repo(self, tmp_path):
        layer = discover_global_layer(
            QWEN_TOOL_SPEC,
            home=tmp_path,
            framework_repo_path=str(tmp_path),
        )
        assert layer.stub_path == str(
            tmp_path / "framework-config" / "qwen" / "stubs" / "stub-qwen-settings.json"
        )

    def test_no_stub_path_without_framework_repo(self, tmp_path):
        layer = discover_global_layer(QWEN_TOOL_SPEC, home=tmp_path)
        assert layer.stub_path is None


class TestQwenProjectLayer:
    """Tests for .qwen/ project stub generation."""

    def test_creates_settings_stub_when_missing(self, tmp_path):
        config_dir = tmp_path / ".qwen"
        created = ensure_qwen_project_layer(config_dir)
        assert created == config_dir / "settings.json"
        assert created is not None
        assert json.loads(created.read_text()) == {}
        assert created.read_text() == QWEN_PROJECT_SETTINGS_STUB

    def test_never_overwrites_existing_settings(self, tmp_path):
        config_dir = tmp_path / ".qwen"
        config_dir.mkdir(parents=True)
        settings = config_dir / "settings.json"
        settings.write_text('{"custom": true}')
        created = ensure_qwen_project_layer(config_dir)
        assert created is None
        assert settings.read_text() == '{"custom": true}'
