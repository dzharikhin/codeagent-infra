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


def _generate_devcontainer_json(ctx: GenerationContext) -> None:
    """Generate .opencode/devcontainer.json."""
    
    if ctx.devcontainer_strategy == "extend" and ctx.existing_devcontainer:
        devcontainer = _generate_extended_devcontainer(ctx)
    else:
        devcontainer = _generate_scratch_devcontainer(ctx)
    
    dc_path = ctx.opencode_dir / "devcontainer.json"
    dc_path.write_text(json.dumps(devcontainer, indent=2) + "\n")


def _get_launch_command(optional_features: List[str]) -> str:
    """Get the host-side devcontainer launch command.
    
    When Docker support is selected, the host-side devcontainer CLI must be
    invoked with DOCKER_CONTEXT=rootless to use the rootless Docker context.
    """
    base_cmd = "devcontainer up --config .opencode/devcontainer.json --workspace-folder ."
    if "docker" in optional_features:
        return f"DOCKER_CONTEXT=rootless {base_cmd}"
    return base_cmd


def _generate_scratch_devcontainer(ctx: GenerationContext) -> dict:
    """Generate devcontainer config from scratch."""
    features = {
        "ghcr.io/devcontainers/features/common-utils:2": {
            "installZsh": False,
            "configureZshAsDefaultShell": False,
        },
        "ghcr.io/devcontainers/features/git:1": {},
        "ghcr.io/stu-bell/devcontainer-features/open-code:0": {
            "open_code_version": "${localEnv:OPENCODE_VERSION:latest}",
        },
    }
    
    _add_optional_features(features, ctx.optional_features, ctx.editor_choice)
    
    mounts = _build_mounts(ctx)
    
    remote_env = {
        "OPENCODE_CONFIG": "/opt/ocframework/config" if ctx.global_settings.framework_config_path else "",
    }
    
    if ctx.editor_choice != "none":
        remote_env["EDITOR"] = ctx.editor_choice
    
    devcontainer = {
        "name": f"OpenCode - {ctx.repo_root.name}",
        "image": "${localEnv:OCF_BASE_IMAGE:mcr.microsoft.com/devcontainers/base:ubuntu-22.04}",
        "features": features,
        "workspaceFolder": "/workspace",
        "workspaceMount": f"source={ctx.repo_root},target=/workspace,type=bind",
        "mounts": mounts,
        "remoteEnv": remote_env,
        "customizations": {
            "vscode": {
                "extensions": [],
            },
        },
        "remoteUser": "${localEnv:OCF_REMOTE_USER:vscode}",
        "postAttachCommand": "bash -lic 'exec opencode'",
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
    features.setdefault("ghcr.io/stu-bell/devcontainer-features/open-code:0", {
        "open_code_version": "${localEnv:OPENCODE_VERSION:latest}",
    })
    
    _add_optional_features(features, ctx.optional_features, ctx.editor_choice)
    
    mounts = existing.get("mounts", [])
    mounts.extend(_build_mounts(ctx))
    
    remote_env = existing.get("remoteEnv", {})
    remote_env["OPENCODE_CONFIG"] = "/opt/ocframework/config" if ctx.global_settings.framework_config_path else ""
    
    if ctx.editor_choice != "none":
        remote_env["EDITOR"] = ctx.editor_choice
    
    remote_user = existing.get("remoteUser", "${localEnv:OCF_REMOTE_USER:vscode}")
    
    devcontainer = {
        "name": f"OpenCode - {ctx.repo_root.name}",
        "features": features,
        "workspaceFolder": "/workspace",
        "workspaceMount": f"source={ctx.repo_root},target=/workspace,type=bind",
        "mounts": mounts,
        "remoteEnv": remote_env,
        "customizations": existing.get("customizations", {"vscode": {"extensions": []}}),
        "remoteUser": remote_user,
        "postAttachCommand": "bash -lic 'exec opencode'",
    }
    
    if "image" in existing:
        devcontainer["image"] = existing["image"]
    elif "build" in existing:
        devcontainer["build"] = existing["build"]
    else:
        devcontainer["image"] = "${localEnv:OCF_BASE_IMAGE:mcr.microsoft.com/devcontainers/base:ubuntu-22.04}"
    
    return devcontainer


def _add_optional_features(features: dict, optional_features: List[str], editor_choice: str = "none") -> None:
    """Add optional features to the features dict.
    
    Uses variable substitution for configurable values with defaults.
    """
    if "docker" in optional_features:
        features["ghcr.io/devcontainers/features/docker-in-docker:2"] = {
            "version": "${localEnv:OCF_DOCKER_FEATURE_VERSION:latest}",
            "enableNonRootDocker": True,
        }
    
    if "python" in optional_features:
        features["ghcr.io/devcontainers/features/python:1"] = {
            "version": "${localEnv:OCF_PYTHON_VERSION:3.12}",
            "installPoetry": True,
        }
    
    if "nodejs" in optional_features:
        features["ghcr.io/devcontainers/features/node:1"] = {
            "version": "${localEnv:OCF_NODE_VERSION:lts}",
        }
    
    if "java" in optional_features:
        features["ghcr.io/devcontainers/features/java:1"] = {
            "version": "${localEnv:OCF_JAVA_VERSION:17}",
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


def _build_mounts(ctx: GenerationContext) -> List[dict]:
    """Build mount list for devcontainer.
    
    Mount policy per security-model.md:
    - Project source: RW (via workspaceMount) - includes all .opencode files
    - Global config: RO
    - Framework config: RO
    - auth.json: RO
    
    Local .opencode files are accessible via the project root workspaceMount,
    no need for explicit mounts.
    """
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
    
    if global_settings.framework_config_path:
        mounts.append({
            "source": global_settings.framework_config_path,
            "target": "/opt/ocframework/config",
            "type": "bind",
            "readOnly": True,
        })
    
    return mounts


def _generate_env_file(ctx: GenerationContext) -> None:
    """Generate .opencode/.env.
    
    .env is override-only - contains only commented examples, no defaults.
    Defaults live in devcontainer.json ${localEnv:VAR:default} syntax.
    """
    lines = [
        "# OpenCode Framework Runtime Configuration",
        "# Override defaults by uncommenting and setting values below.",
        "# All defaults are defined in devcontainer.json.",
        "",
        f"# OPENCODE_VERSION={__version__}",
        "",
        "# Remote user in container (default: vscode)",
        "# OCF_REMOTE_USER=vscode",
        "",
        "# Base container image",
        "# OCF_BASE_IMAGE=mcr.microsoft.com/devcontainers/base:ubuntu-22.04",
    ]
    
    if ctx.editor_choice != "none":
        lines.append("")
        lines.append(f"# Editor preference")
        lines.append(f"EDITOR={ctx.editor_choice}")
    
    feature_vars = []
    if "python" in ctx.optional_features:
        feature_vars.append("# OCF_PYTHON_VERSION=3.12")
    if "nodejs" in ctx.optional_features:
        feature_vars.append("# OCF_NODE_VERSION=lts")
    if "java" in ctx.optional_features:
        feature_vars.append("# OCF_JAVA_VERSION=17")
    if "docker" in ctx.optional_features:
        feature_vars.append("# OCF_DOCKER_FEATURE_VERSION=latest")
    
    if feature_vars:
        lines.append("")
        lines.append("# Feature versions (uncomment to override defaults)")
        lines.extend(feature_vars)
    
    lines.extend([
        "",
        "# Default models for the agent",
        "# DEFAULT_MODEL=",
        "# SMALL_MODEL=",
        "",
        "# Provider base URL overrides",
        "# OPENAI_BASE_URL=",
        "# ANTHROPIC_BASE_URL=",
        "",
    ])
    
    env_content = "\n".join(lines)
    env_path = ctx.opencode_dir / ".env"
    env_path.write_text(env_content)


def _generate_readme(ctx: GenerationContext) -> None:
    """Generate .opencode/README.md."""
    launch_cmd = _get_launch_command(ctx.optional_features)
    
    readme_content = f"""# OpenCode Framework Configuration

This directory contains the project-level configuration for the OpenCode Framework.

## Structure

- `devcontainer.json` - DevContainer configuration for the agent runtime
- `.env` - Runtime environment variables
- `runtime_data/` - Mutable runtime state (not versioned)

## Launch

To start the development environment:

```sh
{launch_cmd}
```

OpenCode is started on attach via `postAttachCommand` in devcontainer.json.

## Version Control

This directory is a linked Git worktree on branch `{ctx.branch_name}`.

To save configuration changes:
1. `cd .opencode`
2. `git add . && git commit -m "Update config"`
3. `git push origin {ctx.branch_name}`

The `.opencode/` directory is a linked Git worktree. Git commands must run
from inside `.opencode/` to affect the configuration branch.

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
