"""Devcontainer file generation."""

import json
import re
from typing import List, Tuple

from .base import FileGenerator, GenerationContext
from .templates import TemplateHandler

COMMON_UTILS_URL = "ghcr.io/devcontainers/features/common-utils:2"


class DevcontainerGenerator(FileGenerator):
    """Generates .opencode/devcontainer.json for build configuration."""
    
    PLACEHOLDER_DOCKERFILE_INITIALIZER = "{{DOCKERFILE_INITIALIZER}}"

    FEATURE_URL_MAP: dict = {
        "docker": "ghcr.io/devcontainers/features/docker-in-docker:2",
        "python": "ghcr.io/devcontainers/features/python:1",
        "nodejs": "ghcr.io/devcontainers/features/node:1",
        "java": "ghcr.io/devcontainers/features/java:1",
    }

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
            "installMaven": True,
        },
    }
    
    def generate(self, ctx: GenerationContext) -> None:
        """Generate devcontainer configuration (build-only)."""
        devcontainer = self._generate_scratch(ctx)
        
        dc_path = ctx.opencode_dir / "devcontainer.json"
        dc_path.write_text(json.dumps(devcontainer, indent=2) + "\n")
    
    @staticmethod
    def _load_template() -> dict:
        """Load devcontainer template from package resources."""
        return TemplateHandler.load_devcontainer_template()
    
    @staticmethod
    def _escape_for_echo_e(content: str) -> str:
        """Escape content for use in shell echo -e command.
        
        Escapes:
        - Backslashes: \ -> \\
        - Double quotes: " -> \"
        - Dollar signs: $ -> \$ (except devcontainer variables)
        
        Devcontainer variables (${localEnv:...}, ${localWorkspaceFolderBasename})
        are preserved without escaping.
        """
        result = content
        result = result.replace("\\", "\\\\")
        result = result.replace('"', '\\"')
        result = re.sub(
            r'\$(?!\{localEnv:)(?!\{localWorkspaceFolderBasename)',
            r'\\$',
            result
        )
        return result
    
    @staticmethod
    def _build_dockerfile_initializer() -> str:
        """Build the initializeCommand for Dockerfile generation.
        
        Loads the dockerfile template and formats it as an echo -e command
        that writes the Dockerfile to .opencode/runtime_data/Dockerfile.
        
        Returns:
            Shell command string for initializeCommand
        """
        dockerfile_content = TemplateHandler.load_dockerfile_template()
        escaped_content = DevcontainerGenerator._escape_for_echo_e(dockerfile_content)
        return f'echo -e "{escaped_content}" > .opencode/runtime_data/Dockerfile'
    
    def _generate_scratch(self, ctx: GenerationContext) -> dict:
        """Generate devcontainer config from template (build-only)."""
        template = DevcontainerGenerator._load_template()
        
        features = dict(template.get("features", {}))
        self._add_optional_features(features, ctx.optional_features, ctx.editor_choice)
        
        devcontainer = dict(template)
        devcontainer["features"] = features
        
        if self.PLACEHOLDER_DOCKERFILE_INITIALIZER in devcontainer.get("initializeCommand", ""):
            devcontainer["initializeCommand"] = self._build_dockerfile_initializer()
        
        return devcontainer
    
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
        editor_choice: str = "none"
    ) -> None:
        """Add optional features to the features dict.

        Uses variable substitution for configurable values with defaults.
        """
        for key in optional_features:
            DevcontainerGenerator._add_one_feature(features, key)

        if editor_choice != "none":
            common_utils = features.get(
                COMMON_UTILS_URL, {}
            )
            packages = common_utils.get("installPackages", [])
            if isinstance(packages, str):
                packages = [p.strip() for p in packages.split() if p.strip()]
            if editor_choice == "vi" and "vim" not in packages:
                packages.append("vim")
            elif editor_choice == "nano" and "nano" not in packages:
                packages.append("nano")
            common_utils["installPackages"] = " ".join(packages) if packages else None
            features[COMMON_UTILS_URL] = common_utils

    @staticmethod
    def _detect_editor(features: dict) -> str:
        """Detect editor preference from common-utils installPackages."""
        common_utils = features.get(COMMON_UTILS_URL, {})
        if not isinstance(common_utils, dict):
            return "none"
        packages = common_utils.get("installPackages", [])
        if isinstance(packages, str):
            pkg_list = packages.split()
        else:
            pkg_list = list(packages) if packages else []
        if "vim" in pkg_list:
            return "vi"
        if "nano" in pkg_list:
            return "nano"
        return "none"

    @classmethod
    def detect(cls, devcontainer: dict) -> Tuple[List[str], str]:
        """Detect currently-enabled optional features and editor choice.

        Args:
            devcontainer: Parsed devcontainer.json content

        Returns:
            Tuple of (optional_features list, editor_choice)
        """
        raw_features = devcontainer.get("features", {})
        features = raw_features if isinstance(raw_features, dict) else {}
        detected = [
            key for key, url in cls.FEATURE_URL_MAP.items() if url in features
        ]
        editor = cls._detect_editor(features)
        return detected, editor

    @staticmethod
    def _set_editor(features: dict, editor_choice: str) -> None:
        """Set the editor preference, adding or removing vim/nano as needed.

        Unlike the init-time guard in _add_optional_features, this fully
        manages the editor packages so toggling to 'none' removes them.
        """
        if editor_choice == "none" and COMMON_UTILS_URL not in features:
            return
        common_utils = features.get(COMMON_UTILS_URL, {})
        if not isinstance(common_utils, dict):
            common_utils = {}
        packages = common_utils.get("installPackages", [])
        if isinstance(packages, str):
            packages = [p.strip() for p in packages.split() if p.strip()]
        elif packages is None:
            packages = []
        else:
            packages = list(packages)
        packages = [p for p in packages if p not in ("vim", "nano")]
        if editor_choice == "vi":
            packages.append("vim")
        elif editor_choice == "nano":
            packages.append("nano")
        common_utils["installPackages"] = " ".join(packages) if packages else None
        features[COMMON_UTILS_URL] = common_utils

    @classmethod
    def apply_delta(
        cls,
        devcontainer: dict,
        add: List[str],
        remove: List[str],
        editor: str,
    ) -> dict:
        """Surgically apply feature/editor changes to a devcontainer dict.

        Mutates the features dict in place, preserving any features and
        parameters that are not part of the requested change.

        Args:
            devcontainer: Parsed devcontainer.json content (mutated)
            add: Feature keys to add
            remove: Feature keys to remove
            editor: Target editor choice ("none", "vi", or "nano")

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
        cls._set_editor(features, editor)
        return devcontainer
