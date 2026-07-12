"""Interactive devcontainer feature management for rebuilds."""

import json
import sys
from pathlib import Path
from typing import List, Optional, Tuple

import click
import typer

from opencode_framework.preflight import check_docker_rootless_context

# Shared feature catalog (key, human-readable description).
# Order matters: it defines the prompt order and is reused by the init wizard.
AVAILABLE_FEATURES: List[Tuple[str, str]] = [
    ("docker", "Docker access (DinD with rootless context)"),
    ("python", "Python + Poetry + uv"),
    ("nodejs", "Node.js + npm"),
    ("java", "Java (JDK)"),
]

JAVA_BUILD_TOOLS = ["maven", "gradle"]

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
    if (
        key == "docker"
        and not currently_enabled
        and not check_docker_rootless_context()
    ):
        typer.secho(
            "    Warning: No rootless Docker context found. "
            "Docker access requires a 'rootless' context.",
            fg=typer.colors.RED,
        )
        typer.echo(_DOCKER_ROOTLESS_HINT)
        return typer.confirm(
            "    Enable Docker anyway? (Not recommended)", default=False
        )
    return True


def _prompt_java_build_tools(current_tools: Optional[List[str]] = None) -> List[str]:
    """Prompt user to select Java build tools (Maven and/or Gradle).

    Args:
        current_tools: Currently enabled build tools (for defaults). If None, defaults to maven only.

    Returns:
        List of enabled build tools (e.g. ["maven"], ["gradle"], ["maven","gradle"])
    """
    typer.echo("\nJava build tools:")

    cur = current_tools or []
    maven = typer.confirm("  Install Maven?", default=("maven" in cur) if cur else True)
    gradle = typer.confirm("  Install Gradle?", default=("gradle" in cur))

    tools: List[str] = []
    if maven:
        tools.append("maven")
    if gradle:
        tools.append("gradle")

    return tools


def prompt_feature_changes(
    current_features: List[str],
    current_editor: str,
    current_java_build_tools: Optional[List[str]] = None,
) -> Tuple[List[str], str, List[str]]:
    """Show the feature selection menu, pre-filled with the current state.

    Args:
        current_features: Currently-enabled feature keys
        current_editor: Current editor choice ("none", "vi", "nano")
        current_java_build_tools: Currently enabled Java build tools (for defaults)

    Returns:
        Tuple of (selected_features, editor_choice, java_build_tools)
    """
    typer.echo("\nCurrent feature configuration:")
    typer.echo(
        f"  Features: {', '.join(current_features) if current_features else '(none)'}"
    )
    typer.echo(f"  Editor: {current_editor}")
    typer.echo("\nSelect features:")

    selected: List[str] = []
    java_build_tools: List[str] = list(current_java_build_tools or [])

    for key, desc in AVAILABLE_FEATURES:
        if _prompt_single_feature(key, desc, key in current_features):
            selected.append(key)
            if key == "java":
                java_build_tools = _prompt_java_build_tools(java_build_tools)
        elif key == "java":
            java_build_tools = []

    editor_choice = typer.prompt(
        "\nEditor preference",
        type=click.Choice(EDITOR_CHOICES),
        default=current_editor,
    )

    return selected, editor_choice, java_build_tools


def parse_port_mappings(raw: str) -> List[str]:
    """Parse a comma-separated port string into a list of port specs.

    Empty/blank entries are dropped.  Specs are passed through verbatim
    (no validation of internals).

    Args:
        raw: Comma-separated string (e.g. "8080:8080, 3000:3000")

    Returns:
        List of port specs (e.g. ["8080:8080", "3000:3000"])
    """
    return [p.strip() for p in raw.split(",") if p.strip()]


def prompt_port_mappings(current_ports: Optional[List[str]] = None) -> List[str]:
    """Prompt for port mappings as comma-separated Docker-style strings.

    Args:
        current_ports: Existing port mappings (pre-fills the default on rebuild)

    Returns:
        List of port specs
    """
    if current_ports is None:
        current_ports = []
    default_str = ", ".join(current_ports)
    raw = typer.prompt(
        "\nPort mappings (host:container, comma-separated; blank for none)",
        default=default_str,
        show_default=bool(current_ports),
    )
    return parse_port_mappings(raw)


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
    current_java_build_tools = DevcontainerGenerator.detect_build_tools(devcontainer)
    new_features, new_editor, new_java_build_tools = prompt_feature_changes(
        current_features, current_editor, current_java_build_tools
    )

    compose_path = opencode_dir / "docker-compose.yaml"
    compose_text = ""
    current_ports: List[str] = []
    if compose_path.exists():
        compose_text = compose_path.read_text()
        current_ports = ComposeGenerator.detect_ports(compose_text)
        new_ports = prompt_port_mappings(current_ports)
    else:
        new_ports = []

    features_changed = (
        set(new_features) != set(current_features) or new_editor != current_editor
        or set(new_java_build_tools) != set(current_java_build_tools)
    )
    ports_changed = new_ports != current_ports

    if not features_changed and not ports_changed:
        typer.echo("No changes; rebuilding with current configuration.")
        return False

    if features_changed:
        add = [f for f in new_features if f not in current_features]
        remove = [f for f in current_features if f not in new_features]
        DevcontainerGenerator.apply_delta(
            devcontainer,
            add=add,
            remove=remove,
            editor=new_editor,
            java_build_tools=new_java_build_tools,
        )
        devcontainer_path.write_text(json.dumps(devcontainer, indent=2) + "\n")
        typer.secho("Updated .opencode/devcontainer.json", fg=typer.colors.GREEN)

    if compose_path.exists() and (features_changed or ports_changed):
        compose_path.write_text(
            ComposeGenerator.rebuild_features(
                compose_text,
                repo_name,
                new_features,
                port_mappings=new_ports,
                java_build_tools=new_java_build_tools,
            )
        )
        typer.secho("Updated .opencode/docker-compose.yaml", fg=typer.colors.GREEN)

    return True
