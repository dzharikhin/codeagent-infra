"""Tests for agent config layers: env migration, discovery, stubs."""

import json

from opencode_framework.agent.layers import (
    ENV_RENAMES,
    QWEN_PROJECT_SETTINGS_STUB,
    discover_global_layer,
    ensure_qwen_project_layer,
    migrate_env_content,
    migrate_env_file,
)
from opencode_framework.agent.registry import OPENCODE_TOOL_SPEC, QWEN_TOOL_SPEC


class TestEnvRenames:
    """Tests for the rename mapping."""

    def test_contains_exactly_the_five_renames(self):
        assert ENV_RENAMES == {
            "OPENCODE_VERSION": "OCF_AGENT_VERSION",
            "OCF_LOCAL_GLOBAL_CONFIG_PATH": "OCF_GLOBAL_CONFIG_PATH",
            "OCF_LOCAL_GLOBAL_AUTH_PATH": "OCF_GLOBAL_AUTH_PATH",
            "PLAN_MAX_BEFORE_RESPONSE_STEPS": "OCF_PLAN_MAX_BEFORE_RESPONSE_STEPS",
            "BUILD_MAX_BEFORE_RESPONSE_STEPS": "OCF_BUILD_MAX_BEFORE_RESPONSE_STEPS",
        }

    def test_new_names_are_not_rename_sources(self):
        assert not set(ENV_RENAMES.values()) & set(ENV_RENAMES)


class TestMigrateEnvContent:
    """Tests for pure .env content migration."""

    def test_renames_key_preserving_value(self):
        content, migrated = migrate_env_content("OPENCODE_VERSION=1.2.3\n")
        assert content == "OCF_AGENT_VERSION=1.2.3\n"
        assert migrated == ["OPENCODE_VERSION"]

    def test_preserves_user_keys_comments_and_order(self):
        original = (
            "# comment about OPENCODE_VERSION=not-a-key\n"
            "REMOTE_USER=root\n"
            "OPENCODE_VERSION=1.2.3\n"
            "\n"
            "MY_CUSTOM_KEY=keep-me\n"
            "OCF_LOCAL_GLOBAL_AUTH_PATH=/tmp/auth.json\n"
        )
        content, migrated = migrate_env_content(original)
        assert content == (
            "# comment about OPENCODE_VERSION=not-a-key\n"
            "REMOTE_USER=root\n"
            "OCF_AGENT_VERSION=1.2.3\n"
            "\n"
            "MY_CUSTOM_KEY=keep-me\n"
            "OCF_GLOBAL_AUTH_PATH=/tmp/auth.json\n"
        )
        assert migrated == [
            "OPENCODE_VERSION",
            "OCF_LOCAL_GLOBAL_AUTH_PATH",
        ]

    def test_value_containing_equals_is_preserved(self):
        content, _ = migrate_env_content("PLAN_MAX_BEFORE_RESPONSE_STEPS=a=b\n")
        assert content == "OCF_PLAN_MAX_BEFORE_RESPONSE_STEPS=a=b\n"

    def test_idempotent_second_pass_is_noop(self):
        first, migrated = migrate_env_content("OPENCODE_VERSION=1.2.3\nOTHER=x\n")
        second, migrated_again = migrate_env_content(first)
        assert second == first
        assert migrated_again == []
        assert migrated == ["OPENCODE_VERSION"]

    def test_content_without_renamable_keys_unchanged(self):
        original = "REMOTE_USER=root\n# nothing to do\n"
        content, migrated = migrate_env_content(original)
        assert content == original
        assert migrated == []


class TestMigrateEnvFile:
    """Tests for in-place .env file migration."""

    def test_writes_renamed_keys_and_returns_old_keys(self, tmp_path):
        env_path = tmp_path / ".env"
        env_path.write_text("OPENCODE_VERSION=1.2.3\nREMOTE_USER=root\n")
        migrated = migrate_env_file(env_path)
        assert migrated == ["OPENCODE_VERSION"]
        assert env_path.read_text() == ("OCF_AGENT_VERSION=1.2.3\nREMOTE_USER=root\n")

    def test_untouched_when_nothing_to_migrate(self, tmp_path):
        env_path = tmp_path / ".env"
        original = "OCF_AGENT_VERSION=latest\nUSER_KEY=1\n"
        env_path.write_text(original)
        migrated = migrate_env_file(env_path)
        assert migrated == []
        assert env_path.read_text() == original


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
        created = ensure_qwen_project_layer(tmp_path)
        assert created == tmp_path / ".qwen" / "settings.json"
        assert created is not None
        assert json.loads(created.read_text()) == {}
        assert created.read_text() == QWEN_PROJECT_SETTINGS_STUB

    def test_never_overwrites_existing_settings(self, tmp_path):
        settings = tmp_path / ".qwen" / "settings.json"
        settings.parent.mkdir(parents=True)
        settings.write_text('{"custom": true}')
        created = ensure_qwen_project_layer(tmp_path)
        assert created is None
        assert settings.read_text() == '{"custom": true}'
