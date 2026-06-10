"""Devcontainer file generation."""

import json
import re
from typing import List

from .base import FileGenerator, GenerationContext
from .templates import TemplateHandler


class DevcontainerGenerator(FileGenerator):
    """Generates .opencode/devcontainer.json for build configuration."""
    
    PLACEHOLDER_DOCKERFILE_INITIALIZER = "{{DOCKERFILE_INITIALIZER}}"
    
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
    def _add_optional_features(
        features: dict, 
        optional_features: List[str], 
        editor_choice: str = "none"
    ) -> None:
        """Add optional features to the features dict.
        
        Uses variable substitution for configurable values with defaults.
        """
        if "docker" in optional_features:
            features["ghcr.io/devcontainers/features/docker-in-docker:2"] = {
                "version": "${localEnv:DOCKER_FEATURE_VERSION:latest}",
                "moby": False,
            }
        
        if "python" in optional_features:
            features["ghcr.io/devcontainers/features/python:1"] = {
                "version": "${localEnv:PYTHON_VERSION:3.14}",
                "toolsToInstall": "uv,poetry,virtualenv,pipenv,black,pytest",
            }
        
        if "nodejs" in optional_features:
            features["ghcr.io/devcontainers/features/node:1"] = {
                "version": "${localEnv:NODE_VERSION:lts}",
            }
        
        if "java" in optional_features:
            features["ghcr.io/devcontainers/features/java:1"] = {
                "version": "${localEnv:JAVA_VERSION:17}",
                "installMaven": True,
            }
        
        if editor_choice != "none":
            common_utils = features.get(
                "ghcr.io/devcontainers/features/common-utils:2", {}
            )
            packages = common_utils.get("installPackages", [])
            if isinstance(packages, str):
                packages = [p.strip() for p in packages.split() if p.strip()]
            if editor_choice == "vi" and "vim" not in packages:
                packages.append("vim")
            elif editor_choice == "nano" and "nano" not in packages:
                packages.append("nano")
            common_utils["installPackages"] = " ".join(packages) if packages else None
            features["ghcr.io/devcontainers/features/common-utils:2"] = common_utils
