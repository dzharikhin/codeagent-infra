"""Generator for .opencode/ directory contents."""

from dataclasses import dataclass
from datetime import datetime
from importlib.resources import files
from pathlib import Path
from typing import Dict, List, Optional
import json
import shutil

from opencode_framework.wizard import WizardResult
from opencode_framework.config import discover_global_settings, GlobalSettings


@dataclass
class GenerationContext:
    """Context for generating .opencode/ contents."""
    
    repo_root: Path
    opencode_dir: Path
    branch_name: str
    devcontainer_strategy: str
    optional_features: List[str]
    editor_choice: str
    global_settings: GlobalSettings
    existing_devcontainer: Optional[dict] = None


def backup_existing_opencode(repo_root: Path) -> Optional[Path]:
    """Backup existing .opencode/ directory.
    
    Creates .opencode.backup-<timestamp> in project root.
    """
    opencode_dir = repo_root / ".opencode"
    if not opencode_dir.exists():
        return None
    
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    backup_path = repo_root / f".opencode.backup-{timestamp}"
    
    shutil.move(str(opencode_dir), str(backup_path))
    return backup_path


def generate_opencode_directory(repo_root: Path, wizard_result: WizardResult) -> None:
    """Generate the .opencode/ directory with all contents.
    
    Assumes the .opencode/ directory already exists (created as worktree).
    """
    opencode_dir = repo_root / ".opencode"
    
    if not opencode_dir.exists():
        opencode_dir.mkdir(parents=True, exist_ok=True)
    
    existing_dc = None
    if wizard_result.existing_devcontainer:
        existing_dc = wizard_result.existing_devcontainer.content
    
    ctx = GenerationContext(
        repo_root=repo_root,
        opencode_dir=opencode_dir,
        branch_name=wizard_result.branch_name,
        devcontainer_strategy=wizard_result.devcontainer_strategy,
        optional_features=wizard_result.optional_features,
        editor_choice=wizard_result.editor_choice,
        global_settings=discover_global_settings(),
        existing_devcontainer=existing_dc,
    )
    
    _generate_devcontainer_json(ctx)
    _generate_env_file(ctx)
    _generate_readme(ctx)
    _generate_gitignore(ctx)
    _generate_runtime_data(ctx)


def _load_devcontainer_template() -> dict:
    """Load devcontainer template from package resources."""
    content = files("opencode_framework.templates").joinpath("devcontainer.template.json").read_text()
    return json.loads(content)


def _load_env_template() -> str:
    """Load env template from package resources."""
    return files("opencode_framework.templates").joinpath("env.template").read_text()


def _generate_devcontainer_json(ctx: GenerationContext) -> None:
    """Generate .opencode/devcontainer.json."""
    
    if ctx.devcontainer_strategy == "extend" and ctx.existing_devcontainer:
        devcontainer = _generate_extended_devcontainer(ctx)
    else:
        devcontainer = _generate_scratch_devcontainer(ctx)
    
    dc_path = ctx.opencode_dir / "devcontainer.json"
    dc_path.write_text(json.dumps(devcontainer, indent=2) + "\n")


def _get_launch_commands() -> Dict[str, str]:
    """Get the host-side devcontainer commands.
    
    All commands source .opencode/.env before execution.
    DOCKER_CONTEXT is set in .env, not in command rendering.
    """
    base_prefix = "set -o allexport; source .opencode/.env;"
    config_arg = "--config .opencode/devcontainer.json --workspace-folder ."
    
    return {
        "launch": f"{base_prefix} devcontainer up {config_arg}",
        "debug": f"{base_prefix} devcontainer exec {config_arg} opencode debug config",
        "shell": f"{base_prefix} devcontainer exec {config_arg} $(devcontainer exec {config_arg} grep $REMOTE_USER /etc/passwd | cut -d: -f7)",
    }


def _generate_scratch_devcontainer(ctx: GenerationContext) -> dict:
    """Generate devcontainer config from template."""
    template = _load_devcontainer_template()
    
    features = dict(template.get("features", {}))
    
    _add_optional_features(features, ctx.optional_features, ctx.editor_choice)
    
    devcontainer = dict(template)
    devcontainer["features"] = features
    
    if ctx.editor_choice != "none":
        remote_env = dict(devcontainer.get("remoteEnv", {}))
        remote_env["EDITOR"] = ctx.editor_choice
        devcontainer["remoteEnv"] = remote_env
    
    return devcontainer


def _generate_extended_devcontainer(ctx: GenerationContext) -> dict:
    """Generate extended devcontainer config using additive merge.
    
    Preserves all existing project-specific config.
    Adds only OpenCode-managed additions from template.
    """
    existing = ctx.existing_devcontainer or {}
    template = _load_devcontainer_template()
    
    features = dict(existing.get("features", {}))
    template_features = template.get("features", {})
    
    for feature_name, feature_config in template_features.items():
        if feature_name not in features:
            features[feature_name] = feature_config
    
    _add_optional_features(features, ctx.optional_features, ctx.editor_choice)
    
    mounts = list(existing.get("mounts", []))
    template_mounts = template.get("mounts", [])
    mounts = _merge_mounts(mounts, template_mounts)
    
    remote_env = dict(existing.get("remoteEnv", {}))
    template_remote_env = template.get("remoteEnv", {})
    for key, value in template_remote_env.items():
        if key not in remote_env:
            remote_env[key] = value
    
    if ctx.editor_choice != "none":
        remote_env["EDITOR"] = ctx.editor_choice
    
    run_args = list(existing.get("runArgs", []))
    template_run_args = template.get("runArgs", [])
    run_args = _merge_run_args(run_args, template_run_args)
    
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


def _extract_mount_target(mount) -> Optional[str]:
    """Extract target path from a mount (string or dict form)."""
    if isinstance(mount, dict):
        return mount.get("target")
    elif isinstance(mount, str):
        for part in mount.split(","):
            if part.startswith("target="):
                return part[7:]
    return None


def _merge_mounts(existing: List, additions: List) -> List:
    """Merge mount lists, deduplicating by target path.
    
    Supports both string mounts and dict mounts.
    """
    result = list(existing)
    existing_targets = {_extract_mount_target(m) for m in existing if _extract_mount_target(m)}
    
    for mount in additions:
        target = _extract_mount_target(mount)
        if target and target not in existing_targets:
            result.append(mount)
    
    return result


def _merge_run_args(existing: List, additions: List) -> List:
    """Merge runArgs lists, avoiding duplicates."""
    result = list(existing)
    
    for i, item in enumerate(additions):
        if item not in result:
            result.append(item)
    
    return result


def _add_optional_features(features: dict, optional_features: List[str], editor_choice: str = "none") -> None:
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
        common_utils = features.get("ghcr.io/devcontainers/features/common-utils:2", {})
        packages = common_utils.get("installPackages", [])
        if isinstance(packages, str):
            packages = [p.strip() for p in packages.split() if p.strip()]
        if editor_choice == "vi" and "vim" not in packages:
            packages.append("vim")
        elif editor_choice == "nano" and "nano" not in packages:
            packages.append("nano")
        common_utils["installPackages"] = " ".join(packages) if packages else None
        features["ghcr.io/devcontainers/features/common-utils:2"] = common_utils


def _generate_env_file(ctx: GenerationContext) -> None:
    """Generate .opencode/.env from template.
    
    Template contains defaults with placeholders for detected paths.
    """
    template = _load_env_template()
    
    settings = ctx.global_settings
    
    replacements = {
        "{{OCF_LOCAL_GLOBAL_CONFIG_PATH}}": settings.global_config_path or "",
        "{{OCF_LOCAL_GLOBAL_AUTH_PATH}}": settings.global_auth_path or "",
        "{{OCF_LOCAL_FRAMEWORK_PATH}}": settings.framework_repo_path or "",
    }
    
    env_content = template
    for placeholder, value in replacements.items():
        env_content = env_content.replace(placeholder, value)
    
    env_path = ctx.opencode_dir / ".env"
    env_path.write_text(env_content)


def _generate_readme(ctx: GenerationContext) -> None:
    """Generate .opencode/README.md."""
    commands = _get_launch_commands()
    
    readme_content = f"""# OpenCode Framework Configuration

This directory contains the project-level configuration for the OpenCode Framework.

## Structure

- `devcontainer.json` - DevContainer configuration for the agent runtime
- `.env` - Runtime environment variables
- `runtime_data/` - Mutable runtime state (not versioned)

## Commands

### Launch

```sh
{commands['launch']}
```

### Debug

```sh
{commands['debug']}
```

### Shell

```sh
{commands['shell']}
```

OpenCode is started on attach via `postAttachCommand` in devcontainer.json.

## Teardown

There is no `devcontainer down` flow yet. To stop and remove the container:

```sh
docker rm -f <project-base-path>
```

## Version Control

This directory is a linked Git worktree on branch `{ctx.branch_name}`.

To save configuration changes:
1. `cd .opencode`
2. `git add . && git commit -m "Update config"`
3. `git push origin {ctx.branch_name}`

The `.opencode/` directory is a linked Git worktree. Git commands must run
from inside `.opencode/` to affect the configuration branch.

## Documentation

- Framework docs: https://github.com/dzharikhin/codeagent-infra
- OpenCode docs: https://opencode.ai
"""
    
    readme_path = ctx.opencode_dir / "README.md"
    readme_path.write_text(readme_content)


def _generate_gitignore(ctx: GenerationContext) -> None:
    """Generate .opencode/.gitignore."""
    gitignore_content = """# Runtime data - not intended for versioning
runtime_data/

# Node modules (created by bun install for OpenCode plugins)
node_modules/

# Local overrides
.env.local
*.local.json
"""
    
    gitignore_path = ctx.opencode_dir / ".gitignore"
    gitignore_path.write_text(gitignore_content)


def _generate_runtime_data(ctx: GenerationContext) -> None:
    """Create .opencode/runtime_data/ directory structure.
    
    Only creates XDG-backed directories that are actually mounted:
    - .cache/
    - .local/share/
    - .local/state/
    """
    runtime_data = ctx.opencode_dir / "runtime_data"
    runtime_data.mkdir(exist_ok=True)
    
    subdirs = [
        ".cache",
        ".local/share",
        ".local/state",
    ]
    
    for subdir in subdirs:
        dir_path = runtime_data / subdir
        dir_path.mkdir(parents=True, exist_ok=True)
