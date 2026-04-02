"""Devcontainer file generation."""

import json
from typing import List

from .base import FileGenerator, GenerationContext
from .templates import TemplateHandler


class DevcontainerGenerator(FileGenerator):
    """Generates .opencode/devcontainer.json for build configuration."""
    
    def generate(self, ctx: GenerationContext) -> None:
        """Generate devcontainer configuration (build-only)."""
        if ctx.devcontainer_strategy == "extend" and ctx.existing_devcontainer:
            devcontainer = self._generate_extended(ctx)
        else:
            devcontainer = self._generate_scratch(ctx)
        
        dc_path = ctx.opencode_dir / "devcontainer.json"
        dc_path.write_text(json.dumps(devcontainer, indent=2) + "\n")
    
    @staticmethod
    def _load_template() -> dict:
        """Load devcontainer template from package resources."""
        return TemplateHandler.load_devcontainer_template()
    
    def _generate_scratch(self, ctx: GenerationContext) -> dict:
        """Generate devcontainer config from template (build-only)."""
        template = DevcontainerGenerator._load_template()
        
        features = dict(template.get("features", {}))
        self._add_optional_features(features, ctx.optional_features, ctx.editor_choice)
        
        devcontainer = dict(template)
        devcontainer["features"] = features
        
        return devcontainer
    
    def _generate_extended(self, ctx: GenerationContext) -> dict:
        """Generate extended devcontainer config using additive merge.
        
        Preserves all existing project-specific config.
        Adds only OpenCode-managed additions from template (build features only).
        """
        existing = ctx.existing_devcontainer or {}
        template = DevcontainerGenerator._load_template()
        
        features = dict(existing.get("features", {}))
        template_features = template.get("features", {})
        
        for feature_name, feature_config in template_features.items():
            if feature_name not in features:
                features[feature_name] = feature_config
        
        self._add_optional_features(features, ctx.optional_features, ctx.editor_choice)
        
        devcontainer = {
            "name": f"OpenCode - {ctx.repo_root.name}",
            "features": features,
            "workspaceFolder": existing.get("workspaceFolder", template.get("workspaceFolder")),
            "workspaceMount": existing.get("workspaceMount", template.get("workspaceMount")),
            "customizations": existing.get("customizations", template.get("customizations")),
            "containerUser": existing.get("containerUser", template.get("containerUser")),
            "remoteUser": existing.get("remoteUser", template.get("remoteUser")),
        }
        
        if "image" in existing:
            devcontainer["image"] = existing["image"]
        elif "build" in existing:
            devcontainer["build"] = existing["build"]
        else:
            devcontainer["image"] = template.get("image")
        
        if "$schema" in template:
            devcontainer["$schema"] = template["$schema"]
        
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
                "version": "${localEnv:PYTHON_VERSION:3.12}",
                "installPoetry": True,
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
