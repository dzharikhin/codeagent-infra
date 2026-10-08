"""Interactive devcontainer feature management for rebuilds."""

import json
import sys
from pathlib import Path
from typing import List, Optional, Tuple

import typer

from opencode_framework.config import (
    host_gitconfig_path,
    host_m2_settings_path,
    host_npmrc_path,
    host_ssh_dir_path,
)
from opencode_framework.generators.templates import (
    GRADLE_ENV_COMMENT,
    GRADLE_OPTS_LINE,
)
from opencode_framework.sandbox.compose import ComposeGenerator
from opencode_framework.sandbox.devcontainer import DevcontainerGenerator

# Shared feature catalog (key, human-readable description).
# Order matters: it defines the prompt order and is reused by the init wizard.
AVAILABLE_FEATURES: List[Tuple[str, str]] = [
    ("docker", "Docker CLI (rootless Podman engine)"),
    ("python", "Python + Poetry + uv"),
    ("nodejs", "Node.js + npm"),
    ("java", "Java (JDK)"),
    ("ssh", "SSH keys and config from host (~/.ssh mirrored read-only)"),
]

JAVA_BUILD_TOOLS = ["maven", "gradle"]


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
    """Prompt to enable/disable one feature.

    Returns True if the feature should be enabled.
    """
    return typer.confirm(f"  Enable {desc}?", default=currently_enabled)


def _prompt_java_build_tools(current_tools: Optional[List[str]] = None) -> List[str]:
    """Prompt user to select Java build tools (Maven and/or Gradle).

    Args:
        current_tools: Currently enabled build tools (for prompt defaults).
            With no current tools both prompts default to No.

    Returns:
        List of enabled build tools (e.g. ["maven"], ["gradle"], ["maven","gradle"])
    """
    typer.echo("\nJava build tools:")

    cur = current_tools or []
    maven = typer.confirm("  Install Maven?", default=("maven" in cur))
    gradle = typer.confirm("  Install Gradle?", default=("gradle" in cur))

    tools: List[str] = []
    if maven:
        tools.append("maven")
    if gradle:
        tools.append("gradle")

    return tools


def prompt_feature_changes(
    current_features: List[str],
    current_java_build_tools: Optional[List[str]] = None,
) -> Tuple[List[str], List[str]]:
    """Show the feature selection menu, pre-filled with the current state.

    Args:
        current_features: Currently-enabled feature keys
        current_java_build_tools: Currently enabled Java build tools (for defaults)

    Returns:
        Tuple of (selected_features, java_build_tools)
    """
    typer.echo("\nCurrent feature configuration:")
    typer.echo(
        f"  Features: {', '.join(current_features) if current_features else '(none)'}"
    )
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

    return selected, java_build_tools


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


def reconcile_env_for_features(
    env_path: Path,
    java_build_tools: List[str],
    ssh_enabled: bool = False,
) -> bool:
    """Reconcile feature-dependent entries in the config worktree's .env.

    Surgically updates (never regenerates) the ``OCF_NPMRC_PATH``,
    ``OCF_M2_SETTINGS_PATH``, ``OCF_GITCONFIG_PATH`` and
    ``OCF_SSH_DIR_PATH`` host-mirror values and the managed
    ``GRADLE_OPTS`` line to match the final feature selection and the
    current host file state; all other lines are preserved verbatim.
    When Gradle is enabled an existing ``GRADLE_OPTS`` line is pinned to
    the managed daemonless value; when disabled only lines matching the
    managed value (and its comment) are removed, so custom values
    survive.

    Args:
        env_path: Path to the config worktree's .env file.
        java_build_tools: Final Java build tool selection
            (e.g. ["maven"], ["gradle"], ["maven", "gradle"]).
        ssh_enabled: Whether the ssh feature is enabled; gates the
            ``OCF_SSH_DIR_PATH`` value.

    Returns:
        True when the file content changed.
    """
    text = env_path.read_text()
    lines = text.splitlines()

    desired_values = {
        "OCF_NPMRC_PATH": host_npmrc_path(),
        "OCF_M2_SETTINGS_PATH": host_m2_settings_path("maven" in java_build_tools),
        "OCF_GITCONFIG_PATH": host_gitconfig_path(),
        "OCF_SSH_DIR_PATH": host_ssh_dir_path(ssh_enabled),
    }
    have_gradle = "gradle" in java_build_tools

    out: List[str] = []
    seen = {key: False for key in desired_values}
    seen_gradle = False

    for line in lines:
        key_match = next(
            (
                key
                for key in desired_values
                if line.startswith(f"{key}=") or line.startswith(f"export {key}=")
            ),
            None,
        )
        if key_match:
            if not seen[key_match]:
                seen[key_match] = True
                out.append(f"{key_match}={desired_values[key_match]}")
            continue
        if line.startswith("GRADLE_OPTS=") or line.startswith("export GRADLE_OPTS="):
            if have_gradle:
                if not seen_gradle:
                    seen_gradle = True
                    out.append(GRADLE_OPTS_LINE)
            elif line == GRADLE_OPTS_LINE:
                continue  # managed line from a previous render: drop
            else:
                out.append(line)
            continue
        if not have_gradle and line == GRADLE_ENV_COMMENT:
            continue
        out.append(line)

    def _insert_after(prefix: str, new_lines: List[str]) -> None:
        for i, existing in enumerate(out):
            if existing.startswith(prefix):
                out[i + 1 : i + 1] = new_lines
                return
        out.extend(new_lines)

    if not seen["OCF_NPMRC_PATH"]:
        _insert_after(
            "OCF_REMOTE_FRAMEWORK_CONFIG_PATH=",
            [f"OCF_NPMRC_PATH={desired_values['OCF_NPMRC_PATH']}"],
        )
    if not seen["OCF_M2_SETTINGS_PATH"]:
        _insert_after(
            "OCF_NPMRC_PATH=",
            [f"OCF_M2_SETTINGS_PATH={desired_values['OCF_M2_SETTINGS_PATH']}"],
        )
    if have_gradle and not seen_gradle:
        _insert_after(
            "OCF_M2_SETTINGS_PATH=",
            [GRADLE_ENV_COMMENT, GRADLE_OPTS_LINE],
        )
    if not seen["OCF_GITCONFIG_PATH"]:
        # Template order is npmrc < m2 < gradle block < gitconfig < ssh;
        # when gradle is on its managed line is guaranteed present here
        # (pre-existing or just inserted), so anchor past it, else past
        # the m2 line.
        gitconfig_anchor = GRADLE_OPTS_LINE if have_gradle else "OCF_M2_SETTINGS_PATH="
        _insert_after(
            gitconfig_anchor,
            [f"OCF_GITCONFIG_PATH={desired_values['OCF_GITCONFIG_PATH']}"],
        )
    if not seen["OCF_SSH_DIR_PATH"]:
        _insert_after(
            "OCF_GITCONFIG_PATH=",
            [f"OCF_SSH_DIR_PATH={desired_values['OCF_SSH_DIR_PATH']}"],
        )

    trailing = "\n" if text.endswith("\n") else ""
    new_text = "\n".join(out) + trailing
    if new_text == text:
        return False
    env_path.write_text(new_text)
    return True


def update_features(
    config_dir: Path,
    repo_name: str,
    agent_tool: str,
    podman_caps: bool = False,
    same: bool = False,
) -> bool:
    """Reconcile devcontainer features across a rebuild.

    Reads the current configuration, prompts for feature/port changes
    (prompts are skipped silently when stdin is not a TTY or when
    ``same`` is set — the detected selection is then used as-is, so
    non-interactive runs still reconcile), and surgically updates
    devcontainer.json and
    docker-compose.yaml when anything changes. The Dockerfile-generating
        ``initializeCommand`` is always re-rendered from current framework
        code so image-level fixes (podman engine setup, containers.conf
        changes, the managed podman package list) propagate through
        ``reconfigure`` instead of freezing at
        harness-creation time; legacy feature keys (docker-in-docker:2) are
    migrated to the podman representation. The .env is always
    reconciled (host dotfile mirror paths, managed GRADLE_OPTS line) to
    match the final feature selection and current host file state.

    Args:
        config_dir: Path to the agent tool's config worktree
            (e.g. .opencode/, .qwen/ or .dsh/)
        repo_name: Repository name (used in managed compose volume names)
        agent_tool: Agent tool name ("opencode" | "qwen" | "dsh"); drives the
            tool-suffixed volume names and entrypoint binary written by
            the compose reconciler
        podman_caps: Caps-mode selector for the docker feature, forwarded
            to the compose reconciler and the Dockerfile initializer
            (rootless outer daemon detection)
        same: Force the non-interactive path even on a TTY (the
            ``reconfigure --same`` mode): keep the detected selection,
            skip all prompts, still reconcile

    Returns:
        True if any managed file was changed, False otherwise.
    """
    devcontainer_path = config_dir / "devcontainer.json"
    try:
        original_dc_text = devcontainer_path.read_text()
        devcontainer = json.loads(original_dc_text)
    except (OSError, ValueError) as exc:
        typer.secho(
            f"Warning: could not read {devcontainer_path} ({exc}); "
            "skipping feature selection.",
            fg=typer.colors.YELLOW,
        )
        return False

    current_features = DevcontainerGenerator.detect(devcontainer)
    current_java_build_tools = DevcontainerGenerator.detect_build_tools(devcontainer)

    interactive = is_interactive() and not same
    if interactive:
        new_features, new_java_build_tools = prompt_feature_changes(
            current_features, current_java_build_tools
        )
    else:
        new_features = list(current_features)
        new_java_build_tools = list(current_java_build_tools)

    compose_path = config_dir / "docker-compose.yaml"
    compose_text = ""
    current_ports: List[str] = []
    new_ports: List[str] = []
    if compose_path.exists():
        compose_text = compose_path.read_text()
        current_ports = ComposeGenerator.detect_ports(compose_text)
        if interactive:
            new_ports = prompt_port_mappings(current_ports)
        else:
            new_ports = list(current_ports)

    features_changed = set(new_features) != set(current_features) or set(
        new_java_build_tools
    ) != set(current_java_build_tools)

    if features_changed:
        add = [f for f in new_features if f not in current_features]
        remove = [f for f in current_features if f not in new_features]
        DevcontainerGenerator.apply_delta(
            devcontainer,
            add=add,
            remove=remove,
            java_build_tools=new_java_build_tools,
        )

    # Refresh the managed podman package list whenever the docker feature
    # stays active, even with an unchanged selection: package-level image
    # fixes (e.g. nftables for netavark) must propagate via reconfigure
    # instead of freezing at harness-creation time. The merge is
    # idempotent and preserves unrelated/custom packages.
    if "docker" in new_features:
        raw_features = devcontainer.setdefault("features", {})
        if isinstance(raw_features, dict):
            DevcontainerGenerator._add_one_feature(raw_features, "docker")

    # Migrate the legacy docker-in-docker feature key (pre-podman
    # harnesses): detect() reports it as "docker", but the stale key
    # must leave the features dict and the podman packages must be
    # merged for the rebuilt image to carry the podman engine.
    legacy_migrated = DevcontainerGenerator.migrate_legacy_dind(
        devcontainer, new_features
    )

    # Always re-render the Dockerfile initializer from current code: the
    # generated Dockerfile content must track the framework, not
    # harness-creation time (devcontainer.json is rewritten whenever the
    # serialized content differs — feature changes, legacy migration, or
    # an initializer drift from an older framework version).
    initializer = DevcontainerGenerator._build_dockerfile_initializer(
        agent_tool, new_features, podman_caps
    )
    devcontainer["initializeCommand"] = initializer
    new_dc_text = json.dumps(devcontainer, indent=2) + "\n"
    dc_changed = new_dc_text != original_dc_text
    if dc_changed:
        devcontainer_path.write_text(new_dc_text)
        typer.secho(
            f"Updated {config_dir.name}/devcontainer.json", fg=typer.colors.GREEN
        )

    # Always reconcile the compose file to match the declared feature set,
    # even when the user made no selection change. This restores any managed
    # footprints (e.g. the docker named volume, security block, entrypoint)
    # that may be missing from a stale or hand-edited compose.
    changed = features_changed or legacy_migrated or dc_changed

    # Reconcile the feature-dependent .env entries (host dotfile mirror
    # paths, managed GRADLE_OPTS line) even when the selection is
    # unchanged: host files may have appeared or disappeared since init.
    if "ssh" in new_features and not host_ssh_dir_path(True):
        typer.secho(
            "Warning: ssh feature selected but ~/.ssh does not exist on "
            "the host; the SSH mirror will be omitted. Re-run "
            "'ocframework reconfigure' after creating it.",
            fg=typer.colors.YELLOW,
        )
    env_path = config_dir / ".env"
    if env_path.is_file() and reconcile_env_for_features(
        env_path, new_java_build_tools, ssh_enabled="ssh" in new_features
    ):
        typer.secho(f"Updated {config_dir.name}/.env", fg=typer.colors.GREEN)
        changed = True

    if compose_path.exists():
        reconciled = ComposeGenerator.rebuild_features(
            compose_text,
            repo_name,
            new_features,
            port_mappings=new_ports,
            java_build_tools=new_java_build_tools,
            agent_tool=agent_tool,
            podman_caps=podman_caps,
        )
        if reconciled != compose_text:
            compose_path.write_text(reconciled)
            typer.secho(
                f"Updated {config_dir.name}/docker-compose.yaml",
                fg=typer.colors.GREEN,
            )
            changed = True

    if not changed:
        typer.echo("No changes; rebuilding with current configuration.")

    return changed
