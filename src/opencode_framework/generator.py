"""Generator for .opencode/ directory contents."""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Optional
import json
import shutil

from opencode_framework.wizard import WizardResult
from opencode_framework.preflight import PreflightResult
from opencode_framework.config import discover_global_settings, GlobalSettings
from opencode_framework import __version__


@dataclass
class GenerationContext:
    """Context for generating .opencode/ contents."""
    
    repo_root: Path
    opencode_dir: Path
    branch_name: str
    devcontainer_strategy: str
    optional_features: List[str]
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
        global_settings=discover_global_settings(),
        existing_devcontainer=existing_dc,
    )
    
    _generate_devcontainer_json(ctx)
    _generate_env_file(ctx)
    _generate_readme(ctx)
    _generate_gitignore(ctx)
    _generate_runtime_data(ctx)
    _generate_opencode_config(ctx)


def _generate_devcontainer_json(ctx: GenerationContext) -> None:
    """Generate .opencode/devcontainer.json."""
    
    if ctx.devcontainer_strategy == "extend" and ctx.existing_devcontainer:
        devcontainer = _generate_extended_devcontainer(ctx)
    else:
        devcontainer = _generate_scratch_devcontainer(ctx)
    
    dc_path = ctx.opencode_dir / "devcontainer.json"
    dc_path.write_text(json.dumps(devcontainer, indent=2) + "\n")


def _generate_scratch_devcontainer(ctx: GenerationContext) -> dict:
    """Generate devcontainer config from scratch."""
    features = {
        "ghcr.io/devcontainers/features/common-utils:2": {
            "installZsh": False,
            "configureZshAsDefaultShell": False,
        },
        "ghcr.io/devcontainers/features/git:1": {},
    }
    
    _add_optional_features(features, ctx.optional_features)
    
    mounts = _build_mounts(ctx)
    
    devcontainer = {
        "name": f"OpenCode - {ctx.repo_root.name}",
        "image": "mcr.microsoft.com/devcontainers/base:ubuntu-22.04",
        "features": features,
        "workspaceFolder": "/workspace",
        "workspaceMount": f"source={ctx.repo_root},target=/workspace,type=bind",
        "mounts": mounts,
        "postCreateCommand": "which opencode || echo 'opencode not found'",
        "postStartCommand": "opencode || echo 'opencode failed to start'",
        "customizations": {
            "vscode": {
                "extensions": [],
            },
        },
        "remoteUser": "vscode",
    }
    
    if "docker" in ctx.optional_features:
        devcontainer["remoteEnv"] = {
            "DOCKER_CONTEXT": "rootless",
        }
    
    return devcontainer


def _generate_extended_devcontainer(ctx: GenerationContext) -> dict:
    """Generate extended devcontainer config from existing devcontainer."""
    existing = ctx.existing_devcontainer or {}
    
    features = existing.get("features", {})
    features.setdefault("ghcr.io/devcontainers/features/common-utils:2", {
        "installZsh": False,
        "configureZshAsDefaultShell": False,
    })
    features.setdefault("ghcr.io/devcontainers/features/git:1", {})
    
    _add_optional_features(features, ctx.optional_features)
    
    mounts = existing.get("mounts", [])
    mounts.extend(_build_mounts(ctx))
    
    devcontainer = {
        "name": f"OpenCode - {ctx.repo_root.name}",
        "features": features,
        "workspaceFolder": "/workspace",
        "workspaceMount": f"source={ctx.repo_root},target=/workspace,type=bind",
        "mounts": mounts,
        "postCreateCommand": "which opencode || echo 'opencode not found'",
        "postStartCommand": "opencode || echo 'opencode failed to start'",
        "customizations": existing.get("customizations", {"vscode": {"extensions": []}}),
        "remoteUser": existing.get("remoteUser", "vscode"),
    }
    
    if "image" in existing:
        devcontainer["image"] = existing["image"]
    elif "build" in existing:
        devcontainer["build"] = existing["build"]
    else:
        devcontainer["image"] = "mcr.microsoft.com/devcontainers/base:ubuntu-22.04"
    
    if "docker" in ctx.optional_features:
        existing_env = existing.get("remoteEnv", {})
        existing_env["DOCKER_CONTEXT"] = "rootless"
        devcontainer["remoteEnv"] = existing_env
    
    return devcontainer


def _add_optional_features(features: dict, optional_features: List[str]) -> None:
    """Add optional features to the features dict."""
    if "docker" in optional_features:
        features["ghcr.io/devcontainers/features/docker-in-docker:2"] = {
            "version": "latest",
            "enableNonRootDocker": True,
        }
    
    if "python" in optional_features:
        features["ghcr.io/devcontainers/features/python:1"] = {
            "version": "3.12",
            "installPoetry": True,
        }
    
    if "nodejs" in optional_features:
        features["ghcr.io/devcontainers/features/node:1"] = {
            "version": "lts",
        }
    
    if "java" in optional_features:
        features["ghcr.io/devcontainers/features/java:1"] = {
            "version": "17",
            "installMaven": True,
        }
    
    if "vi" in optional_features or "nano" in optional_features:
        common_utils = features.get("ghcr.io/devcontainers/features/common-utils:2", {})
        packages = common_utils.get("installPackages", [])
        if isinstance(packages, str):
            packages = [p.strip() for p in packages.split() if p.strip()]
        if "vi" in optional_features and "vim" not in packages:
            packages.append("vim")
        if "nano" in optional_features and "nano" not in packages:
            packages.append("nano")
        common_utils["installPackages"] = " ".join(packages) if packages else None
        features["ghcr.io/devcontainers/features/common-utils:2"] = common_utils


def _build_mounts(ctx: GenerationContext) -> List[dict]:
    """Build mount list for devcontainer."""
    mounts = []
    
    global_settings = ctx.global_settings
    if global_settings.global_config_found:
        mounts.append({
            "source": global_settings.global_config_path,
            "target": "/home/vscode/.config/opencode",
            "type": "bind",
            "readOnly": True,
        })
    
    if global_settings.global_auth_found:
        mounts.append({
            "source": global_settings.global_auth_path,
            "target": "/home/vscode/.local/share/opencode/auth.json",
            "type": "bind",
            "readOnly": True,
        })
    
    return mounts


def _generate_env_file(ctx: GenerationContext) -> None:
    """Generate .opencode/.env."""
    env_content = f"""# OpenCode Framework Runtime Configuration
# Project-level runtime and configuration inputs

OPENCODE_VERSION={__version__}

# Editor preference
# EDITOR=vi

# Default models for the agent
# DEFAULT_MODEL=
# SMALL_MODEL=

# Provider base URL overrides
# OPENAI_BASE_URL=
# ANTHROPIC_BASE_URL=
"""
    
    env_path = ctx.opencode_dir / ".env"
    env_path.write_text(env_content)


def _generate_readme(ctx: GenerationContext) -> None:
    """Generate .opencode/README.md."""
    readme_content = f"""# OpenCode Framework Configuration

This directory contains the project-level configuration for the OpenCode Framework.

## Structure

- `devcontainer.json` - DevContainer configuration for the agent runtime
- `.env` - Runtime environment variables
- `opencode.json` - OpenCode project configuration
- `runtime_data/` - Mutable runtime state (not versioned)

## Launch

To start the development environment:

```sh
devcontainer up --config .opencode/devcontainer.json --workspace-folder .
```

OpenCode will start automatically when the container launches.

## Version Control

This directory is a linked Git worktree on branch `{ctx.branch_name}`.
Commit and push changes to this branch to save your configuration.

## Documentation

- Framework docs: https://github.com/anomalyco/opencode-framework
- OpenCode docs: https://opencode.ai
"""
    
    readme_path = ctx.opencode_dir / "README.md"
    readme_path.write_text(readme_content)


def _generate_gitignore(ctx: GenerationContext) -> None:
    """Generate .opencode/.gitignore."""
    gitignore_content = """# Runtime data - not intended for versioning
runtime_data/

# Local overrides
.env.local
*.local.json
"""
    
    gitignore_path = ctx.opencode_dir / ".gitignore"
    gitignore_path.write_text(gitignore_content)


def _generate_runtime_data(ctx: GenerationContext) -> None:
    """Create .opencode/runtime_data/ directory structure."""
    runtime_data = ctx.opencode_dir / "runtime_data"
    runtime_data.mkdir(exist_ok=True)
    
    subdirs = [
        "logs",
        "caches",
        "tools",
        "temp",
        "sessions",
        "output",
        "home",
    ]
    
    for subdir in subdirs:
        (runtime_data / subdir).mkdir(exist_ok=True)
    
    (runtime_data / ".gitkeep").write_text("")


def _generate_opencode_config(ctx: GenerationContext) -> None:
    """Generate native OpenCode project configuration."""
    opencode_config = {
        "version": __version__,
        "project": {
            "name": ctx.repo_root.name,
            "path": str(ctx.repo_root),
        },
        "permissions": {
            "read": ["*"],
            "edit": ["*"],
            "bash": ["*"],
        },
    }
    
    config_path = ctx.opencode_dir / "opencode.json"
    config_path.write_text(json.dumps(opencode_config, indent=2) + "\n")
