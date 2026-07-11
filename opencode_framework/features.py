"""Interactive devcontainer feature management for rebuilds."""

import json
import sys
from pathlib import Path
from typing import List, Tuple

import click
import typer

from opencode_framework.preflight import check_docker_rootless_context

# Shared feature catalog (key, human-readable description).
# Order matters: it defines the prompt order and is reused by the init wizard.
AVAILABLE_FEATURES: List[Tuple[str, str]] = [
    ("docker", "Docker access (DinD with rootless context)"),
    ("python", "Python + Poetry"),
    ("nodejs", "Node.js + npm"),
    ("java", "Java + Maven"),
]

EDITOR_CHOICES = ["none", "vi", "nano"]

_DOCKER_ROOTLESS_HINT = (
    "    Create it with: docker context create rootless "
    "--docker 'host=unix:///run/user/$(id -u)/docker.sock'"
)


def is_interactive() -> bool:
    """Return True when stdin is a TTY (a human can answer prompts)."""
    try:
        return sys.stdin.isatty()
    except (AttributeError, ValueError):
        return False


def _prompt_single_feature(
    key: str,
    desc: str,
    currently_enabled: bool,
) -> bool:
    """Prompt to enable/disable one feature, with the docker rootless guard.

    Returns True if the feature should be enabled.
    """
    if not typer.confirm(f"  Enable {desc}?", default=currently_enabled):
        return False
    if key == "docker" and not currently_enabled and not check_docker_rootless_context():
        typer.secho(
            "    Warning: No rootless Docker context found. "
            "Docker access requires a 'rootless' context.",
            fg=typer.colors.RED,
        )
        typer.echo(_DOCKER_ROOTLESS_HINT)
        return typer.confirm("    Enable Docker anyway? (Not recommended)", default=False)
    return True


def prompt_feature_changes(
    current_features: List[str],
    current_editor: str,
) -> Tuple[List[str], str]:
    """Show the feature selection menu, pre-filled with the current state.

    Args:
        current_features: Currently-enabled feature keys
        current_editor: Current editor choice ("none", "vi", "nano")

    Returns:
        Tuple of (selected_features, editor_choice)
    """
    typer.echo("\nCurrent feature configuration:")
    typer.echo(
        f"  Features: {', '.join(current_features) if current_features else '(none)'}"
    )
    typer.echo(f"  Editor: {current_editor}")
    typer.echo("\nSelect features:")

    selected: List[str] = []
    for key, desc in AVAILABLE_FEATURES:
        if _prompt_single_feature(key, desc, key in current_features):
            selected.append(key)

    editor_choice = typer.prompt(
        "\nEditor preference",
        type=click.Choice(EDITOR_CHOICES),
        default=current_editor,
    )

    return selected, editor_choice


def update_features(opencode_dir: Path, repo_name: str) -> bool:
    """Interactively offer to add/remove devcontainer features.

    Reads the current configuration, prompts for changes (skipped silently
    when stdin is not a TTY), and surgically updates devcontainer.json and
    docker-compose.yaml when anything changes.

    Args:
        opencode_dir: Path to the .opencode directory
        repo_name: Repository name (used in managed compose volume names)

    Returns:
        True if feature configuration was changed, False otherwise.
    """
    from opencode_framework.generators.compose import ComposeGenerator
    from opencode_framework.generators.devcontainer import DevcontainerGenerator

    if not is_interactive():
        return False

    devcontainer_path = opencode_dir / "devcontainer.json"
    try:
        devcontainer = json.loads(devcontainer_path.read_text())
    except (OSError, ValueError) as exc:
        typer.secho(
            f"Warning: could not read {devcontainer_path} ({exc}); "
            "skipping feature selection.",
            fg=typer.colors.YELLOW,
        )
        return False

    current_features, current_editor = DevcontainerGenerator.detect(devcontainer)
    new_features, new_editor = prompt_feature_changes(current_features, current_editor)

    if set(new_features) == set(current_features) and new_editor == current_editor:
        typer.echo("No feature changes; rebuilding with current configuration.")
        return False

    add = [f for f in new_features if f not in current_features]
    remove = [f for f in current_features if f not in new_features]
    DevcontainerGenerator.apply_delta(devcontainer, add=add, remove=remove, editor=new_editor)
    devcontainer_path.write_text(json.dumps(devcontainer, indent=2) + "\n")
    typer.secho("Updated .opencode/devcontainer.json", fg=typer.colors.GREEN)

    compose_path = opencode_dir / "docker-compose.yaml"
    if compose_path.exists():
        compose_text = compose_path.read_text()
        compose_path.write_text(
            ComposeGenerator.rebuild_features(compose_text, repo_name, new_features)
        )
        typer.secho("Updated .opencode/docker-compose.yaml", fg=typer.colors.GREEN)

    return True
