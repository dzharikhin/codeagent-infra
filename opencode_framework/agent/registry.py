"""Agent tool registry: one ToolSpec per supported agent CLI.

Holds every piece of tool-specific knowledge (opencode, qwen) as frozen
data: binary/service name, serve command, install mechanism, and the
compose/env fragments that fill the agent slots in the sandbox templates
(``{{AGENT_ENV}}``, ``{{AGENT_MOUNTS}}``, ``{{AGENT_FEATURE}}``,
``{{AGENT_INSTALL}}``). Sandbox code consumes these specs but never
defines tool knowledge itself.
"""

from dataclasses import dataclass
from typing import Dict, Literal, Optional, Tuple

from opencode_framework.exceptions import ValidationError

_INDENT = " " * 6


def _mount(source_target: str) -> str:
    """Build one read-only compose volume-mount line (6-space indent)."""
    return f"{_INDENT}- {source_target}:ro"


def _env_line(key: str, value: str) -> str:
    """Build one compose environment-entry line (6-space indent)."""
    return f"{_INDENT}- {key}={value}"


def _nuts_mount(subdir: str, config_dirname: str) -> str:
    """Build the nuts-and-bolts per-tool subdir mount line."""
    source = f"${{OCF_LOCAL_FRAMEWORK_PATH}}/framework-nuts-and-bolts/{subdir}"
    target = (
        f"/{{{{OCF_REPO_ROOT_NAME}}}}/{config_dirname}"
        f"/framework-nuts-and-bolts/{subdir}"
    )
    return _mount(f"{source}:{target}")


@dataclass(frozen=True)
class ServeSpec:
    """How the agent runs in server mode.

    Attributes:
        port: container port the server listens on.
        token_env: environment variable carrying the auth token.
        token_required: whether the tool refuses non-loopback binds
            without a token.
        serve_args: full argument vector after the binary name.
    """

    port: int
    token_env: str
    token_required: bool
    serve_args: Tuple[str, ...]


@dataclass(frozen=True)
class InstallSpec:
    """How the agent binary gets into the sandbox image.

    Exactly one of devcontainer_feature / dockerfile_snippet is set for
    the tools known today; both None means the binary is expected in the
    base image already.
    """

    devcontainer_feature: Optional[str]
    feature_version_env: Optional[str]
    dockerfile_snippet: Optional[str]
    build_args: Tuple[str, ...]

    @property
    def kind(self) -> Literal["feature", "dockerfile", "both", "none"]:
        """Explicit install mode for consumers to branch on."""
        has_feature = self.devcontainer_feature is not None
        has_snippet = self.dockerfile_snippet is not None
        if has_feature and has_snippet:
            return "both"
        if has_feature:
            return "feature"
        if has_snippet:
            return "dockerfile"
        return "none"


@dataclass(frozen=True)
class ToolSpec:
    """Everything the framework needs to know about one agent tool."""

    name: str
    binary: str
    config_dirname: str
    serve: ServeSpec
    install: InstallSpec
    compose_env_fragment: str
    compose_mount_fragment: str
    env_template_fragment: str
    framework_config_subdir: str
    global_config_base: Literal["config_root", "home"]
    global_config_is_dir: bool
    global_config_relpath: Tuple[str, ...]
    global_env_relpath: Tuple[str, ...]
    auth_relpath: Optional[Tuple[str, ...]]
    stub_relpath: Tuple[str, ...]
    context_files: Tuple[str, ...]


_OPENCODE_CONFIG_DIRNAME = ".opencode"
_QWEN_CONFIG_DIRNAME = ".qwen"

_QWEN_DOCKERFILE_INSTALL = (
    "# qwen (Qwen Code) CLI: Node 22 (nodesource) + npm install\n"
    "RUN apt-get update \\\n"
    "    && apt-get install -y --no-install-recommends ca-certificates curl gnupg \\\n"
    "    && mkdir -p /etc/apt/keyrings \\\n"
    "    && curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key \\\n"
    "       | gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg \\\n"
    '    && echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg]'
    ' https://deb.nodesource.com/node_22.x nodistro main" \\\n'
    "       > /etc/apt/sources.list.d/nodesource.list \\\n"
    "    && apt-get update \\\n"
    "    && apt-get install -y --no-install-recommends nodejs \\\n"
    "    && npm install -g @qwen-code/qwen-code@${OCF_AGENT_VERSION} \\\n"
    "    && apt-get purge -y gnupg \\\n"
    "    && apt-get autoremove -y \\\n"
    "    && rm -rf /var/lib/apt/lists/*"
)

_OPENCODE_AUTH_MOUNT = (
    "${OCF_GLOBAL_AUTH_PATH:-/dev/null}:"
    "${XDG_DATA_HOME:-/home/${REMOTE_USER}/.local/share}/opencode/auth.json"
)
_OPENCODE_GLOBAL_DIR_MOUNT = (
    "${OCF_GLOBAL_CONFIG_PATH:-/dev/null}:"
    "${XDG_CONFIG_HOME:-/home/${REMOTE_USER}/.config}/opencode"
)
_QWEN_GLOBAL_FILE_MOUNT = (
    "${OCF_GLOBAL_CONFIG_PATH:-/dev/null}:/opt/ocframework/global/qwen-settings.json"
)
_QWEN_FRAMEWORK_SETTINGS_MOUNT = (
    "${OCF_LOCAL_FRAMEWORK_PATH}/framework-config/qwen/qwen-settings.json:"
    "/home/${REMOTE_USER}/.qwen/settings.json"
)

OPENCODE_TOOL_SPEC = ToolSpec(
    name="opencode",
    binary="opencode",
    config_dirname=_OPENCODE_CONFIG_DIRNAME,
    serve=ServeSpec(
        port=4096,
        token_env="OPENCODE_SERVER_PASSWORD",
        token_required=False,
        serve_args=("serve", "--hostname", "0.0.0.0", "--port", "4096"),
    ),
    install=InstallSpec(
        devcontainer_feature=(
            "ghcr.io/jsburckhardt/devcontainer-features/opencode:1.1.1"
        ),
        feature_version_env="OCF_AGENT_VERSION",
        dockerfile_snippet=None,
        build_args=(),
    ),
    compose_env_fragment="\n".join(
        [
            _env_line(
                "OPENCODE_CONFIG",
                "${OCF_REMOTE_FRAMEWORK_CONFIG_PATH}/opencode/config.json",
            ),
            _env_line(
                "OPENCODE_TUI_CONFIG",
                "${OCF_REMOTE_FRAMEWORK_CONFIG_PATH}/opencode/tui.json",
            ),
        ]
    ),
    compose_mount_fragment="\n".join(
        [
            _mount(_OPENCODE_AUTH_MOUNT),
            _mount(_OPENCODE_GLOBAL_DIR_MOUNT),
            _nuts_mount("common", _OPENCODE_CONFIG_DIRNAME),
            _nuts_mount("opencode", _OPENCODE_CONFIG_DIRNAME),
        ]
    ),
    env_template_fragment=(
        "OCF_AGENT_TOOL=opencode\n"
        "OCF_GLOBAL_CONFIG_PATH={{OCF_GLOBAL_CONFIG_PATH}}\n"
        "OCF_GLOBAL_AUTH_PATH={{OCF_GLOBAL_AUTH_PATH}}"
    ),
    framework_config_subdir="opencode",
    global_config_base="config_root",
    global_config_is_dir=True,
    global_config_relpath=("opencode",),
    global_env_relpath=("opencode", ".env"),
    auth_relpath=("opencode", "auth.json"),
    stub_relpath=("opencode", "stubs", "stub-auth.json"),
    context_files=("AGENTS.md",),
)

QWEN_TOOL_SPEC = ToolSpec(
    name="qwen",
    binary="qwen",
    config_dirname=_QWEN_CONFIG_DIRNAME,
    serve=ServeSpec(
        port=4170,
        token_env="QWEN_SERVER_TOKEN",
        token_required=True,
        serve_args=("serve", "--hostname", "0.0.0.0", "--port", "4170"),
    ),
    install=InstallSpec(
        devcontainer_feature=None,
        feature_version_env=None,
        dockerfile_snippet=_QWEN_DOCKERFILE_INSTALL,
        build_args=("OCF_AGENT_VERSION",),
    ),
    compose_env_fragment=_env_line(
        "QWEN_CODE_SYSTEM_DEFAULTS_PATH",
        "/opt/ocframework/global/qwen-settings.json",
    ),
    compose_mount_fragment="\n".join(
        [
            _mount(_QWEN_GLOBAL_FILE_MOUNT),
            _mount(_QWEN_FRAMEWORK_SETTINGS_MOUNT),
            _nuts_mount("common", _QWEN_CONFIG_DIRNAME),
            _nuts_mount("qwen", _QWEN_CONFIG_DIRNAME),
        ]
    ),
    env_template_fragment=(
        "OCF_AGENT_TOOL=qwen\nOCF_GLOBAL_CONFIG_PATH={{OCF_GLOBAL_CONFIG_PATH}}"
    ),
    framework_config_subdir="qwen",
    global_config_base="home",
    global_config_is_dir=False,
    global_config_relpath=(".qwen", "settings.json"),
    global_env_relpath=(".qwen", ".env"),
    auth_relpath=None,
    stub_relpath=("qwen", "stubs", "stub-qwen-settings.json"),
    context_files=("QWEN.md", "AGENTS.md"),
)

SUPPORTED_TOOLS: Dict[str, ToolSpec] = {
    OPENCODE_TOOL_SPEC.name: OPENCODE_TOOL_SPEC,
    QWEN_TOOL_SPEC.name: QWEN_TOOL_SPEC,
}

DEFAULT_TOOL = "opencode"


def managed_volume_name(prefix: str, repo_name: str, tool: str) -> str:
    """Compose managed volume name, tool-suffixed.

    Each tool gets its own volumes so two agents can run concurrently
    on the same repo without sharing mutable state (docker-in-docker
    in particular must never share a /var/lib/docker volume).
    """
    return f"{prefix}-{repo_name}-{tool}"


def get_tool_spec(name: str) -> ToolSpec:
    """Return the ToolSpec for a tool name.

    Args:
        name: tool identifier ("opencode" | "qwen").

    Returns:
        The frozen ToolSpec for the requested tool.

    Raises:
        ValidationError: if the name is not a supported tool.
    """
    try:
        return SUPPORTED_TOOLS[name]
    except KeyError:
        raise ValidationError(
            message=f"Unsupported agent tool: {name!r}",
            remediation=f"Choose one of: {', '.join(sorted(SUPPORTED_TOOLS))}.",
            context={"requested": name, "supported": sorted(SUPPORTED_TOOLS)},
        ) from None
