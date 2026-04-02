"""Devcontainer file generation."""

import json
from typing import Dict, List, Optional

from .base import FileGenerator, GenerationContext
from .templates import TemplateHandler


class DevcontainerGenerator(FileGenerator):
    """Generates .opencode/devcontainer.json."""
    
    def generate(self, ctx: GenerationContext) -> None:
        """Generate devcontainer configuration."""
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
        """Generate devcontainer config from template."""
        template = DevcontainerGenerator._load_template()
        
        features = dict(template.get("features", {}))
        self._add_optional_features(features, ctx.optional_features, ctx.editor_choice)
        
        devcontainer = dict(template)
        devcontainer["features"] = features
        
        mounts = list(template.get("mounts", []))
        
        if ctx.global_settings.global_config_found and ctx.global_settings.global_config_path:
            config_mount = (
                f"type=bind,source=${{localEnv:OCF_LOCAL_GLOBAL_CONFIG_PATH}},"
                f"target=${{localEnv:XDG_CONFIG_HOME}}/opencode,readonly"
            )
            mounts.append(config_mount)
        
        devcontainer["mounts"] = mounts
        
        if ctx.editor_choice != "none":
            remote_env = dict(devcontainer.get("remoteEnv", {}))
            remote_env["EDITOR"] = "${localEnv:EDITOR}"
            devcontainer["remoteEnv"] = remote_env
        
        return devcontainer
    
    def _generate_extended(self, ctx: GenerationContext) -> dict:
        """Generate extended devcontainer config using additive merge.
        
        Preserves all existing project-specific config.
        Adds only OpenCode-managed additions from template.
        """
        existing = ctx.existing_devcontainer or {}
        template = DevcontainerGenerator._load_template()
        
        features = dict(existing.get("features", {}))
        template_features = template.get("features", {})
        
        for feature_name, feature_config in template_features.items():
            if feature_name not in features:
                features[feature_name] = feature_config
        
        self._add_optional_features(features, ctx.optional_features, ctx.editor_choice)
        
        mounts = list(existing.get("mounts", []))
        template_mounts = template.get("mounts", [])
        mounts = self._merge_mounts(mounts, template_mounts)
        
        if ctx.global_settings.global_config_found and ctx.global_settings.global_config_path:
            config_mount = (
                f"type=bind,source=${{localEnv:OCF_LOCAL_GLOBAL_CONFIG_PATH}},"
                f"target=${{localEnv:XDG_CONFIG_HOME}}/opencode,readonly"
            )
            config_target = "${localEnv:XDG_CONFIG_HOME}/opencode"
            existing_targets = {
                self._extract_mount_target(m) for m in mounts 
                if self._extract_mount_target(m)
            }
            if config_target not in existing_targets:
                mounts.append(config_mount)
        
        remote_env = dict(existing.get("remoteEnv", {}))
        template_remote_env = template.get("remoteEnv", {})
        for key, value in template_remote_env.items():
            if key not in remote_env:
                remote_env[key] = value
        
        if ctx.editor_choice != "none":
            remote_env["EDITOR"] = "${localEnv:EDITOR}"
        
        run_args = list(existing.get("runArgs", []))
        template_run_args = template.get("runArgs", [])
        run_args = self._merge_run_args(run_args, template_run_args)
        
        devcontainer = {
            "name": f"OpenCode - {ctx.repo_root.name}",
            "features": features,
            "workspaceFolder": existing.get("workspaceFolder", template.get("workspaceFolder")),
            "workspaceMount": existing.get("workspaceMount", template.get("workspaceMount")),
            "mounts": mounts,
            "remoteEnv": remote_env,
            "runArgs": run_args,
            "customizations": existing.get("customizations", template.get("customizations")),
            "containerUser": existing.get("containerUser", template.get("containerUser")),
            "remoteUser": existing.get("remoteUser", template.get("remoteUser")),
            "postAttachCommand": template.get("postAttachCommand", "opencode --continue"),
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
    def _extract_mount_target(mount) -> Optional[str]:
        """Extract target path from a mount (string or dict form)."""
        if isinstance(mount, dict):
            return mount.get("target")
        elif isinstance(mount, str):
            for part in mount.split(","):
                if part.startswith("target="):
                    return part[7:]
        return None
    
    @staticmethod
    def _merge_mounts(existing: List, additions: List) -> List:
        """Merge mount lists, deduplicating by target path.
        
        Supports both string mounts and dict mounts.
        """
        result = list(existing)
        existing_targets = {
            DevcontainerGenerator._extract_mount_target(m) for m in existing 
            if DevcontainerGenerator._extract_mount_target(m)
        }
        
        for mount in additions:
            target = DevcontainerGenerator._extract_mount_target(mount)
            if target and target not in existing_targets:
                result.append(mount)
        
        return result
    
    @staticmethod
    def _merge_run_args(existing: List, additions: List) -> List:
        """Merge runArgs lists, avoiding duplicates and excluding --env-file."""
        result = []
        skip_next = False
        
        for item in existing:
            if skip_next:
                skip_next = False
                continue
            if item == "--env-file":
                skip_next = True
                continue
            result.append(item)
        
        for item in additions:
            if item not in result and item != "--env-file":
                result.append(item)
        
        return result
    
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
