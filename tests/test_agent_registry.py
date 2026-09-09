"""Tests for the agent tool registry."""

import dataclasses

import pytest

from opencode_framework.agent.registry import (
    DEFAULT_TOOL,
    OPENCODE_TOOL_SPEC,
    QWEN_TOOL_SPEC,
    SUPPORTED_TOOLS,
    InstallSpec,
    get_tool_spec,
)
from opencode_framework.exceptions import ValidationError


class TestToolRegistry:
    """Tests for registry lookup and module constants."""

    def test_supported_tools_contains_both(self):
        assert set(SUPPORTED_TOOLS) == {"opencode", "qwen"}

    def test_default_tool_is_opencode(self):
        assert DEFAULT_TOOL == "opencode"

    def test_get_tool_spec_returns_opencode(self):
        assert get_tool_spec("opencode") is OPENCODE_TOOL_SPEC

    def test_get_tool_spec_returns_qwen(self):
        assert get_tool_spec("qwen") is QWEN_TOOL_SPEC

    def test_get_tool_spec_unknown_raises(self):
        with pytest.raises(ValidationError) as exc_info:
            get_tool_spec("cursor")
        assert "cursor" in exc_info.value.message
        assert exc_info.value.context["supported"] == ["opencode", "qwen"]
        assert exc_info.value.remediation is not None

    def test_specs_are_frozen(self):
        with pytest.raises(dataclasses.FrozenInstanceError):
            OPENCODE_TOOL_SPEC.binary = "other"


class TestInstallSpecKind:
    """Tests for the explicit install-mode property."""

    def test_feature_only(self):
        spec = InstallSpec("some-feature:1", None, None, ())
        assert spec.kind == "feature"

    def test_dockerfile_only(self):
        spec = InstallSpec(None, None, "RUN echo hi", ())
        assert spec.kind == "dockerfile"

    def test_both(self):
        spec = InstallSpec("some-feature:1", None, "RUN echo hi", ())
        assert spec.kind == "both"

    def test_none(self):
        spec = InstallSpec(None, None, None, ())
        assert spec.kind == "none"

    def test_opencode_installs_via_feature(self):
        assert OPENCODE_TOOL_SPEC.install.kind == "feature"

    def test_qwen_installs_via_dockerfile(self):
        assert QWEN_TOOL_SPEC.install.kind == "dockerfile"


class TestOpencodeSpec:
    """Tests for opencode-specific spec values."""

    def test_binary_and_service_name(self):
        assert OPENCODE_TOOL_SPEC.name == "opencode"
        assert OPENCODE_TOOL_SPEC.binary == "opencode"

    def test_serve_spec(self):
        serve = OPENCODE_TOOL_SPEC.serve
        assert serve.port == 4096
        assert serve.token_env == "OPENCODE_SERVER_PASSWORD"
        assert serve.token_required is False
        assert str(serve.port) in serve.serve_args

    def test_install_uses_devcontainer_feature(self):
        install = OPENCODE_TOOL_SPEC.install
        assert (
            install.devcontainer_feature
            == "ghcr.io/jsburckhardt/devcontainer-features/opencode:1.1.1"
        )
        assert install.feature_version_env == "OCF_AGENT_VERSION"
        assert install.dockerfile_snippet is None
        assert install.build_args == ()

    def test_global_layer_shape(self):
        assert OPENCODE_TOOL_SPEC.global_config_base == "config_root"
        assert OPENCODE_TOOL_SPEC.global_config_is_dir is True
        assert OPENCODE_TOOL_SPEC.global_config_relpath == ("opencode",)
        assert OPENCODE_TOOL_SPEC.auth_relpath == ("opencode", "auth.json")

    def test_stub_relpath(self):
        assert OPENCODE_TOOL_SPEC.stub_relpath == (
            "opencode",
            "stubs",
            "stub-auth.json",
        )

    def test_context_files(self):
        assert OPENCODE_TOOL_SPEC.context_files == ("AGENTS.md",)


class TestQwenSpec:
    """Tests for qwen-specific spec values."""

    def test_binary_and_service_name(self):
        assert QWEN_TOOL_SPEC.name == "qwen"
        assert QWEN_TOOL_SPEC.binary == "qwen"

    def test_serve_spec(self):
        serve = QWEN_TOOL_SPEC.serve
        assert serve.port == 4170
        assert serve.token_env == "QWEN_SERVER_TOKEN"
        assert serve.token_required is True
        assert str(serve.port) in serve.serve_args

    def test_install_uses_dockerfile(self):
        install = QWEN_TOOL_SPEC.install
        assert install.devcontainer_feature is None
        assert install.feature_version_env is None
        assert install.build_args == ("OCF_AGENT_VERSION",)

    def test_dockerfile_snippet_installs_qwen(self):
        snippet = QWEN_TOOL_SPEC.install.dockerfile_snippet
        assert snippet is not None
        assert "deb.nodesource.com/node_22.x" in snippet
        assert "npm install -g @qwen-code/qwen-code@${OCF_AGENT_VERSION}" in snippet

    def test_global_layer_shape(self):
        assert QWEN_TOOL_SPEC.global_config_base == "home"
        assert QWEN_TOOL_SPEC.global_config_is_dir is False
        assert QWEN_TOOL_SPEC.global_config_relpath == (".qwen", "settings.json")
        assert QWEN_TOOL_SPEC.auth_relpath is None

    def test_stub_relpath(self):
        assert QWEN_TOOL_SPEC.stub_relpath == (
            "qwen",
            "stubs",
            "stub-qwen-settings.json",
        )

    def test_context_files(self):
        assert QWEN_TOOL_SPEC.context_files == ("QWEN.md", "AGENTS.md")


class TestComposeEnvFragment:
    """Tests for the {{AGENT_ENV}} fragment content."""

    def test_opencode_fragment_sets_config_vars(self):
        fragment = OPENCODE_TOOL_SPEC.compose_env_fragment
        assert "OPENCODE_CONFIG=" in fragment
        assert "OPENCODE_TUI_CONFIG=" in fragment
        assert "/opencode/config.json" in fragment
        assert "/opencode/tui.json" in fragment

    def test_qwen_fragment_sets_system_defaults_path(self):
        fragment = QWEN_TOOL_SPEC.compose_env_fragment
        assert (
            "QWEN_CODE_SYSTEM_DEFAULTS_PATH=/opt/ocframework/global/"
            "qwen-settings.json" in fragment
        )

    def test_fragment_lines_use_compose_indent(self):
        for fragment in (
            OPENCODE_TOOL_SPEC.compose_env_fragment,
            QWEN_TOOL_SPEC.compose_env_fragment,
        ):
            for line in fragment.splitlines():
                assert line.startswith("      - ")


class TestComposeMountFragment:
    """Tests for the {{AGENT_MOUNTS}} fragment content."""

    def test_opencode_mounts_auth_and_global_dir(self):
        fragment = OPENCODE_TOOL_SPEC.compose_mount_fragment
        assert "${OCF_GLOBAL_AUTH_PATH:-/dev/null}" in fragment
        assert "/opencode/auth.json:ro" in fragment
        assert "${OCF_GLOBAL_CONFIG_PATH:-/dev/null}" in fragment
        assert "/opencode:ro" in fragment

    def test_qwen_mounts_global_and_framework_settings(self):
        fragment = QWEN_TOOL_SPEC.compose_mount_fragment
        assert "/opt/ocframework/global/qwen-settings.json:ro" in fragment
        assert "/home/${REMOTE_USER}/.qwen/settings.json:ro" in fragment

    def test_both_tools_mount_nuts_subdirs(self):
        for spec in (OPENCODE_TOOL_SPEC, QWEN_TOOL_SPEC):
            fragment = spec.compose_mount_fragment
            source = "${OCF_LOCAL_FRAMEWORK_PATH}/framework-nuts-and-bolts"
            target = (
                f"/{{{{OCF_REPO_ROOT_NAME}}}}/{spec.config_dirname}"
                "/framework-nuts-and-bolts"
            )
            assert f"{source}/common:{target}/common:ro" in fragment
            assert f"{source}/{spec.name}:{target}/{spec.name}:ro" in fragment


class TestEnvTemplateFragment:
    """Tests for the .env tool fragment content."""

    def test_opencode_fragment_declares_tool_and_paths(self):
        fragment = OPENCODE_TOOL_SPEC.env_template_fragment
        assert "OCF_AGENT_TOOL=opencode" in fragment
        assert "OCF_GLOBAL_CONFIG_PATH={{OCF_GLOBAL_CONFIG_PATH}}" in fragment
        assert "OCF_GLOBAL_AUTH_PATH={{OCF_GLOBAL_AUTH_PATH}}" in fragment

    def test_qwen_fragment_declares_tool_and_path_without_auth(self):
        fragment = QWEN_TOOL_SPEC.env_template_fragment
        assert "OCF_AGENT_TOOL=qwen" in fragment
        assert "OCF_GLOBAL_CONFIG_PATH={{OCF_GLOBAL_CONFIG_PATH}}" in fragment
        assert "OCF_GLOBAL_AUTH_PATH" not in fragment


class TestGlobalEnvRelpath:
    """Tests for the per-tool global .env relpath."""

    def test_opencode_global_env_relpath(self):
        assert OPENCODE_TOOL_SPEC.global_env_relpath == ("opencode", ".env")

    def test_qwen_global_env_relpath(self):
        assert QWEN_TOOL_SPEC.global_env_relpath == (".qwen", ".env")
