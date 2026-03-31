"""Interactive wizard for setup decisions."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional
import getpass
import os

import click
import typer

from opencode_framework.preflight import PreflightResult, check_docker_rootless_context
from opencode_framework.devcontainer import detect_devcontainer, DevcontainerInfo


@dataclass
class WizardResult:
    """Collected wizard decisions."""
    
    branch_name: str
    devcontainer_strategy: str  # "extend", "from_scratch", or "skip"
    optional_features: List[str]
    existing_devcontainer: Optional[DevcontainerInfo]
    should_add_to_gitignore: bool


def suggest_branch_name() -> str:
    """Suggest a branch name based on username."""
    username = getpass.getuser() or "user"
    return f"codeagent-{username}"


def check_gitignore_needs_opencode(repo_root: Path) -> bool:
    """Check if .gitignore mentions .opencode."""
    gitignore_path = repo_root / ".gitignore"
    if not gitignore_path.is_file():
        return True
    
    content = gitignore_path.read_text()
    return ".opencode" not in content


def run_wizard(repo_root: Path, preflight_result: PreflightResult) -> WizardResult:
    """Run the interactive setup wizard.
    
    Asks only for meaningful structural choices:
    - Branch name with suggested default
    - Devcontainer strategy
    - Optional feature selection
    """
    suggested_branch = suggest_branch_name()
    
    branch_name = typer.prompt(
        "Config branch name",
        default=suggested_branch,
        type=str,
    )
    
    existing_devcontainer = detect_devcontainer(repo_root)
    
    if existing_devcontainer:
        typer.echo(f"\nFound existing devcontainer at: {existing_devcontainer.path}")
        
        if existing_devcontainer.compatible:
            typer.echo("The existing devcontainer appears compatible.")
            strategy = typer.prompt(
                "Devcontainer strategy",
                type=click.Choice(["extend", "from_scratch"]),
                default="extend",
            )
        else:
            typer.secho(
                f"\nThe existing devcontainer is incompatible: {existing_devcontainer.incompatibility_reason}",
                fg=typer.colors.RED,
            )
            typer.echo("\nRecommended action: create a new devcontainer from scratch.")
            typer.echo("To proceed, move or remove the existing devcontainer and re-run init.")
            raise typer.Exit(code=1)
    else:
        typer.echo("\nNo existing devcontainer found.")
        strategy = "from_scratch"
    
    typer.echo("\nOptional features:")
    available_features = [
        ("docker", "Docker access (DinD with rootless context)"),
        ("vi", "vi editor"),
        ("nano", "nano editor"),
        ("python", "Python + Poetry"),
        ("nodejs", "Node.js + npm"),
        ("java", "Java + Maven"),
    ]
    
    optional_features = []
    for feature_key, feature_desc in available_features:
        if feature_key == "docker":
            if typer.confirm(f"  Enable {feature_desc}?", default=False):
                if not check_docker_rootless_context():
                    typer.secho(
                        "    Warning: No rootless Docker context found. Docker access requires a 'rootless' context.",
                        fg=typer.colors.RED,
                    )
                    typer.echo("    Create it with: docker context create rootless --docker 'host=unix:///run/user/$(id -u)/docker.sock'")
                    if typer.confirm("    Enable Docker anyway? (Not recommended)", default=False):
                        optional_features.append(feature_key)
                else:
                    optional_features.append(feature_key)
        else:
            if typer.confirm(f"  Enable {feature_desc}?", default=False):
                optional_features.append(feature_key)
    
    if check_gitignore_needs_opencode(repo_root):
        typer.secho(
            "\nNote: .opencode/ is not in .gitignore. Consider adding it to avoid committing framework files.",
            fg=typer.colors.YELLOW,
        )
    
    return WizardResult(
        branch_name=branch_name,
        devcontainer_strategy=strategy,
        optional_features=optional_features,
        existing_devcontainer=existing_devcontainer,
        should_add_to_gitignore=True,
    )
