"""Devcontainer file generation and feature reconciliation."""

import json
import re
from typing import List, Optional

from opencode_framework.agent.registry import DEFAULT_TOOL, ToolSpec, get_tool_spec
from opencode_framework.generators.base import FileGenerator, GenerationContext
from opencode_framework.generators.templates import TemplateHandler


class DevcontainerGenerator(FileGenerator):
    """Generates devcontainer.json in the tool's config directory."""

    PLACEHOLDER_DOCKERFILE_INITIALIZER = "{{DOCKERFILE_INITIALIZER}}"

    FEATURE_URL_MAP: dict = {
        "docker": "ghcr.io/devcontainers/features/docker-in-docker:2",
        "python": "ghcr.io/devcontainers/features/python:1",
        "nodejs": "ghcr.io/devcontainers/features/node:1",
        "java": "ghcr.io/devcontainers/features/java:1",
    }

    _JAVA_BUILD_TOOL_PARAM = {"maven": "installMaven", "gradle": "installGradle"}

    _FEATURE_DEFAULTS: dict = {
        "docker": {
            "version": "${localEnv:DOCKER_FEATURE_VERSION:latest}",
            "moby": False,
        },
        "python": {
            "version": "${localEnv:PYTHON_VERSION:3.14}",
            "toolsToInstall": "uv,poetry,virtualenv,pipenv,black,pytest",
        },
        "nodejs": {
            "version": "${localEnv:NODE_VERSION:lts}",
        },
        "java": {
            "version": "${localEnv:JAVA_VERSION:17}",
        },
    }

    def generate(self, ctx: GenerationContext) -> None:
        """Generate devcontainer configuration (build-only)."""
        devcontainer = self._generate_scratch(ctx)

        dc_path = ctx.config_dir / "devcontainer.json"
        dc_path.write_text(json.dumps(devcontainer, indent=2) + "\n")

    @staticmethod
    def _load_template() -> dict:
        """Load devcontainer template from package resources."""
        return TemplateHandler.load_devcontainer_template()

    @staticmethod
    def _escape_for_echo_e(content: str) -> str:
        """Escape content for use in shell echo -e command.

        Escapes:
        - Backslashes: \\ -> \\
        - Double quotes: " -> \"
        - Dollar signs: $ -> \\$ (except devcontainer variables)

        Devcontainer variables (${localEnv:...}, ${localWorkspaceFolderBasename})
        are preserved without escaping.
        """
        result = content
        result = result.replace("\\", "\\\\")
        result = result.replace('"', '\\"')
        result = re.sub(
            r"\$(?!\{localEnv:)(?!\{localWorkspaceFolderBasename)", r"\\$", result
        )
        return result

    @staticmethod
    def _build_install_block(spec: ToolSpec) -> str:
        """Build the Dockerfile install block for a tool spec.

        ARG declarations for the spec's build args followed by the
        install snippet; empty when the tool installs via a
        devcontainer feature instead.

        Args:
            spec: Tool spec providing build args and install snippet

        Returns:
            Install block lines, or "" for feature-installed tools
        """
        lines: List[str] = [f"ARG {arg}=latest" for arg in spec.install.build_args]
        if spec.install.dockerfile_snippet:
            lines.append(spec.install.dockerfile_snippet)
        return "\n".join(lines)

    @staticmethod
    def _build_dockerfile_initializer(agent_tool: str = DEFAULT_TOOL) -> str:
        """Build the initializeCommand for Dockerfile generation.

        Loads the dockerfile template, injects the tool's install block
        into the {{AGENT_INSTALL}} slot, and formats it as an echo -e
        command that writes the Dockerfile into the tool's config
        directory (workspace-relative at initializeCommand runtime).

        Args:
            agent_tool: Agent tool name ("opencode" | "qwen")

        Returns:
            Shell command string for initializeCommand
        """
        spec = get_tool_spec(agent_tool)
        dockerfile_content = TemplateHandler.load_dockerfile_template()
        install_block = DevcontainerGenerator._build_install_block(spec)
        if install_block:
            dockerfile_content = dockerfile_content.replace(
                "{{AGENT_INSTALL}}", install_block
            )
        else:
            dockerfile_content = dockerfile_content.replace("\n{{AGENT_INSTALL}}", "")
        escaped_content = DevcontainerGenerator._escape_for_echo_e(dockerfile_content)
        return (
            f'echo -e "{escaped_content}" > '
            f"{spec.config_dirname}/runtime_data/Dockerfile"
        )

    @staticmethod
    def _reconcile_java_build_tools(
        features: dict, java_build_tools: List[str]
    ) -> None:
        """Set installMaven and installGradle flags on the Java feature.

        Args:
            features: The features dict (mutated in place)
            java_build_tools: List of enabled tools (e.g. ["maven"],
                ["gradle"], ["maven", "gradle"])
        """
        java_url = DevcontainerGenerator.FEATURE_URL_MAP["java"]
        if java_url not in features:
            return

        maven_installed = "maven" in java_build_tools
        gradle_installed = "gradle" in java_build_tools

        features[java_url]["installMaven"] = maven_installed
        features[java_url]["installGradle"] = gradle_installed

    def _generate_scratch(self, ctx: GenerationContext) -> dict:
        """Generate devcontainer config from template (build-only)."""
        template = DevcontainerGenerator._load_template()
        spec = get_tool_spec(ctx.agent_tool)

        features = dict(template.get("features", {}))
        devcontainer = dict(template)
        self._add_agent_install(devcontainer, features, spec)
        self._add_optional_features(
            features,
            ctx.optional_features,
            java_build_tools=ctx.java_build_tools,
        )

        devcontainer["features"] = features

        if self.PLACEHOLDER_DOCKERFILE_INITIALIZER in devcontainer.get(
            "initializeCommand", ""
        ):
            devcontainer["initializeCommand"] = self._build_dockerfile_initializer(
                ctx.agent_tool
            )

        return devcontainer

    @staticmethod
    def _add_agent_install(devcontainer: dict, features: dict, spec: ToolSpec) -> None:
        """Fill the agent install slots in the devcontainer config.

        Feature-installed tools get their devcontainer feature entry with
        a localEnv version pin; Dockerfile-installed tools get their
        build args on the build section instead.

        Args:
            devcontainer: Devcontainer config dict (mutated for build args)
            features: Features dict (mutated for feature-installed tools)
            spec: Tool spec providing the install mechanism
        """
        install = spec.install
        if install.devcontainer_feature:
            version_env = install.feature_version_env or "OCF_AGENT_VERSION"
            features[install.devcontainer_feature] = {
                "version": f"${{localEnv:{version_env}:latest}}"
            }
        if install.build_args:
            build = devcontainer.setdefault("build", {})
            build["args"] = {
                arg: f"${{localEnv:{arg}:latest}}" for arg in install.build_args
            }

    @staticmethod
    def _add_one_feature(features: dict, key: str) -> None:
        """Add a single optional feature by its key."""
        url = DevcontainerGenerator.FEATURE_URL_MAP.get(key)
        if url is not None:
            features[url] = dict(DevcontainerGenerator._FEATURE_DEFAULTS[key])

    @staticmethod
    def _remove_one_feature(features: dict, key: str) -> None:
        """Remove a single optional feature by its key."""
        url = DevcontainerGenerator.FEATURE_URL_MAP.get(key)
        if url is not None:
            features.pop(url, None)

    @staticmethod
    def _add_optional_features(
        features: dict,
        optional_features: List[str],
        java_build_tools: Optional[List[str]] = None,
    ) -> None:
        """Add optional features to the features dict.

        Uses variable substitution for configurable values with defaults.
        """
        for key in optional_features:
            DevcontainerGenerator._add_one_feature(features, key)

        # Reconcile Java build tools after all features are added
        if java_build_tools is not None:
            DevcontainerGenerator._reconcile_java_build_tools(
                features, java_build_tools
            )

    @staticmethod
    def detect_build_tools(devcontainer: dict) -> List[str]:
        """Detect currently-enabled Java build tools from devcontainer config.

        Args:
            devcontainer: Parsed devcontainer.json content

        Returns:
            List of enabled build tools (e.g. ["maven"], ["gradle"],
            ["maven","gradle"]). Empty when Java is present without
            explicit install flags.
        """
        raw_features = devcontainer.get("features", {})
        features = raw_features if isinstance(raw_features, dict) else {}
        java_url = DevcontainerGenerator.FEATURE_URL_MAP.get("java")

        if java_url is None or java_url not in features:
            return []

        java_feature = features[java_url]
        if not isinstance(java_feature, dict):
            return []

        tools: List[str] = []
        if java_feature.get("installMaven"):
            tools.append("maven")
        if java_feature.get("installGradle"):
            tools.append("gradle")

        return tools

    @classmethod
    def detect(cls, devcontainer: dict) -> List[str]:
        """Detect currently-enabled optional features.

        Args:
            devcontainer: Parsed devcontainer.json content

        Returns:
            List of enabled optional feature keys
        """
        raw_features = devcontainer.get("features", {})
        features = raw_features if isinstance(raw_features, dict) else {}
        return [key for key, url in cls.FEATURE_URL_MAP.items() if url in features]

    @classmethod
    def apply_delta(
        cls,
        devcontainer: dict,
        add: List[str],
        remove: List[str],
        java_build_tools: Optional[List[str]] = None,
    ) -> dict:
        """Surgically apply feature changes to a devcontainer dict.

        Mutates the features dict in place, preserving any features and
        parameters that are not part of the requested change.

        Args:
            devcontainer: Parsed devcontainer.json content (mutated)
            add: Feature keys to add
            remove: Feature keys to remove
            java_build_tools: List of enabled Java build tools (for reconciliation)

        Returns:
            The same devcontainer dict, mutated.
        """
        raw_features = devcontainer.setdefault("features", {})
        features = raw_features if isinstance(raw_features, dict) else {}
        if raw_features is not features:
            devcontainer["features"] = features
        for key in remove:
            cls._remove_one_feature(features, key)
        for key in add:
            cls._add_one_feature(features, key)

        # Reconcile Java build tools if Java is in the final feature set
        if java_build_tools is not None:
            cls._reconcile_java_build_tools(features, java_build_tools)

        return devcontainer
