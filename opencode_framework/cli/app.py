"""CLI entrypoint for ocframework."""

import json
import re
import secrets
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Dict, List, NoReturn, Optional, Tuple

import typer
from dotenv import dotenv_values

from opencode_framework import __version__
from opencode_framework.agent.discovery import (
    AGENT_TOOL_KEY,
    ConfigLocation,
    discover_configs,
)
from opencode_framework.agent.layers import (
    discover_global_layer,
    expected_global_env_path,
    expected_global_path,
)
from opencode_framework.agent.registry import (
    DEFAULT_TOOL,
    QWEN_TOOL_SPEC,
    SUPPORTED_TOOLS,
    ToolSpec,
)
from opencode_framework.config import (
    discover_global_settings,
    get_config_root,
    get_local_data_home,
)
from opencode_framework.exceptions import PortAllocationError
from opencode_framework.generators import GenerationOrchestrator
from opencode_framework.generators.documentation import DocumentationGenerator
from opencode_framework.git_ops import (
    get_current_branch,
    is_worktree,
    remove_worktree,
    setup_opencode_worktree,
)
from opencode_framework.preflight import (
    get_repo_root,
    run_preflight_checks,
)
from opencode_framework.sandbox.compose import ComposeGenerator
from opencode_framework.sandbox.features import is_interactive, update_features
from opencode_framework.sandbox.net import find_free_port
from opencode_framework.sandbox.runtime import (
    EnvError,
    build_docker_env,
    load_env_with_overrides,
    load_image_id,
    parse_cli_env_vars,
    remove_image_id,
    save_image_id,
    validate_runtime_context,
)
from opencode_framework.wizard import resolve_tool_or_exit, run_wizard

SERVER_HOST_PORT_MIN = 4096
SERVER_HOST_PORT_MAX = 4196

app = typer.Typer(
    name="ocframework",
    help="Framework for attaching AI coding agents to existing projects safely",
    add_completion=False,
    no_args_is_help=False,
)


def _print_version_info() -> None:
    """Print version information including global settings detection."""
    settings = discover_global_settings()

    typer.echo(f"ocframework version: {__version__}")

    framework_path = settings.framework_repo_path
    if framework_path:
        typer.echo(f"framework repo path: {framework_path}")
    else:
        typer.secho("framework repo path: not found", fg=typer.colors.RED)

    expected_global_config_path = get_config_root() / "opencode"
    expected_global_auth_path = get_local_data_home() / "opencode" / "auth.json"

    typer.echo(f"global config found: {settings.global_config_found}")
    if settings.global_config_found:
        typer.echo(f"global config path: {settings.global_config_path}")
    else:
        typer.echo(f"expected global config path: {expected_global_config_path}")
    typer.echo(f"global auth.json found: {settings.global_auth_found}")
    if settings.global_auth_found:
        typer.echo(f"global auth.json path: {settings.global_auth_path}")
    else:
        typer.echo(f"expected global auth.json path: {expected_global_auth_path}")

    qwen_layer = discover_global_layer(QWEN_TOOL_SPEC)
    typer.echo(f"qwen global settings found: {qwen_layer.global_found}")
    if qwen_layer.global_found:
        typer.echo(f"qwen global settings path: {qwen_layer.global_path}")
    else:
        expected_qwen_path = expected_global_path(QWEN_TOOL_SPEC)
        typer.echo(f"expected qwen global settings path: {expected_qwen_path}")


def _peek_env_agent_tool(
    env_file: Optional[Path] = None,
    env_vars: Optional[List[str]] = None,
) -> str:
    """Peek at OCF_AGENT_TOOL from CLI env overrides only.

    Sources are consulted in the precedence the launcher merges them
    (highest first): CLI variables, override file. The config directory's
    .env is deliberately not consulted — launch selects the directory via
    discovery, which cross-checks OCF_AGENT_TOOL against the directory
    itself. Parse failures are tolerated here; the real loader reports
    them later.

    Args:
        env_file: override file from --env-file, when given.
        env_vars: KEY=VALUE strings from -e/--env, when given.

    Returns:
        The first non-empty OCF_AGENT_TOOL value, or "" when absent
        from both sources.
    """
    if env_vars:
        try:
            cli_env = parse_cli_env_vars(env_vars)
        except ValueError:
            cli_env = {}  # reported later by load_env_with_overrides
        value = (cli_env.get(AGENT_TOOL_KEY) or "").strip()
        if value:
            return value

    if env_file is None or not env_file.exists():
        return ""
    try:
        parsed = dotenv_values(env_file, interpolate=False)
    except Exception:
        return ""  # reported later by load_env_with_overrides
    return (parsed.get(AGENT_TOOL_KEY) or "").strip()


def _describe_env_mismatch(loc: ConfigLocation) -> str:
    """One-line explanation of a config directory contradicted by its .env."""
    if loc.env_tool:
        return (
            f"{loc.spec.config_dirname}/.env sets "
            f"{AGENT_TOOL_KEY}={loc.env_tool!r}, but "
            f"{loc.spec.config_dirname}/ is the {loc.spec.name} config directory"
        )
    return (
        f"{loc.spec.config_dirname}/.env does not set {AGENT_TOOL_KEY}, but "
        f"{loc.spec.config_dirname}/ is the {loc.spec.name} config directory"
    )


def _no_such_config_exit(repo_root: Path, spec: ToolSpec) -> NoReturn:
    """Exit when the requested tool has no usable config directory here."""
    if (repo_root / spec.config_dirname).is_dir():
        typer.secho(
            f"Error: {spec.config_dirname}/ exists but is not a framework "
            "config directory (missing .env).",
            fg=typer.colors.RED,
            err=True,
        )
    else:
        typer.secho(
            f"Error: no {spec.config_dirname}/ framework config directory "
            f"for tool '{spec.name}' in this repository.",
            fg=typer.colors.RED,
            err=True,
        )
    typer.secho(
        f"Remediation: run 'ocframework init --tool {spec.name}' "
        "(add --force if the directory already exists).",
        fg=typer.colors.YELLOW,
        err=True,
    )
    raise typer.Exit(1)


def _invalid_config_exit(loc: ConfigLocation) -> NoReturn:
    """Exit on a legacy/hand-edited config; no silent migration."""
    typer.secho(f"Error: {_describe_env_mismatch(loc)}.", fg=typer.colors.RED, err=True)
    typer.secho(
        f"Remediation: run 'ocframework init --force --tool {loc.spec.name}' "
        "to regenerate the configuration.",
        fg=typer.colors.YELLOW,
        err=True,
    )
    raise typer.Exit(1)


def _require_location(
    repo_root: Path,
    locations: List[ConfigLocation],
    spec: ToolSpec,
) -> ConfigLocation:
    """Return the discovered location for spec, exiting when unusable."""
    loc = next((item for item in locations if item.spec.name == spec.name), None)
    if loc is None:
        _no_such_config_exit(repo_root, spec)
    if not loc.valid:
        _invalid_config_exit(loc)
    return loc


def _select_launch_target(
    repo_root: Path,
    tool: Optional[str],
    env_file: Optional[Path],
    env_vars: Optional[List[str]],
) -> Tuple[Path, ToolSpec]:
    """Select the config worktree and ToolSpec to launch.

    Precedence: the --tool option wins; otherwise an OCF_AGENT_TOOL
    override from -e/--env or --env-file; otherwise the single valid
    config directory is auto-selected (prompted when several exist).
    Config directories whose .env contradicts the tool their name implies
    are never launched; they get a re-init remediation instead.

    Args:
        repo_root: project repository root.
        tool: --tool option value, when given.
        env_file: override file from --env-file, when given.
        env_vars: KEY=VALUE strings from -e/--env, when given.

    Returns:
        (config_dir, spec) of the selected config worktree.

    Raises:
        typer.Exit: when no usable config directory matches the request.
    """
    locations = discover_configs(repo_root)

    requested: Optional[ToolSpec] = None
    if tool is not None:
        requested = resolve_tool_or_exit(tool)
    else:
        override = _peek_env_agent_tool(env_file, env_vars)
        if override:
            requested = resolve_tool_or_exit(
                override,
                hint=f"Fix {AGENT_TOOL_KEY} in -e/--env or the --env-file override.",
            )

    if requested is not None:
        loc = _require_location(repo_root, locations, requested)
        if tool is not None:
            override = _peek_env_agent_tool(env_file, env_vars)
            if override and override != requested.name:
                typer.secho(
                    f"Warning: {AGENT_TOOL_KEY}={override!r} from -e/--env or "
                    f"--env-file overrides the selected tool '{requested.name}' "
                    "inside the container environment.",
                    fg=typer.colors.YELLOW,
                )
        typer.echo(f"Using {requested.name} config at {requested.config_dirname}/")
        return loc.config_dir, requested

    valid = [loc for loc in locations if loc.valid]
    invalid = [loc for loc in locations if not loc.valid]

    if len(valid) == 1:
        loc = valid[0]
        typer.echo(f"Using {loc.spec.name} config at {loc.spec.config_dirname}/")
        return loc.config_dir, loc.spec

    if valid:
        if not is_interactive():
            typer.secho(
                "Error: multiple framework config directories found: "
                + ", ".join(loc.spec.config_dirname for loc in valid),
                fg=typer.colors.RED,
                err=True,
            )
            typer.secho(
                "Remediation: pass --tool (opencode | qwen) to choose one.",
                fg=typer.colors.YELLOW,
                err=True,
            )
            raise typer.Exit(1)
        typer.echo("Multiple framework config directories found:")
        for loc in valid:
            branch = get_current_branch(cwd=loc.config_dir)
            suffix = f" ({branch})" if branch else ""
            typer.echo(f"  {loc.spec.name} — {loc.spec.config_dirname}/{suffix}")
        name = typer.prompt(
            "Agent tool to launch", default=valid[0].spec.name, type=str
        )
        spec = resolve_tool_or_exit(name, hint="Choose one of the listed tools.")
        loc = _require_location(repo_root, locations, spec)
        typer.echo(f"Using {spec.name} config at {spec.config_dirname}/")
        return loc.config_dir, spec

    if invalid:
        if len(invalid) == 1:
            _invalid_config_exit(invalid[0])
        for loc in invalid:
            typer.secho(
                f"Error: {_describe_env_mismatch(loc)}.",
                fg=typer.colors.RED,
                err=True,
            )
        typer.secho(
            "Remediation: run 'ocframework init --force --tool <tool>' to "
            "regenerate a config directory.",
            fg=typer.colors.YELLOW,
            err=True,
        )
        raise typer.Exit(1)

    unqualified = sorted(
        spec.config_dirname
        for spec in SUPPORTED_TOOLS.values()
        if (repo_root / spec.config_dirname).is_dir()
    )
    if unqualified:
        for dirname in unqualified:
            typer.secho(
                f"Error: {dirname}/ exists but is not a framework config "
                "directory (missing .env).",
                fg=typer.colors.RED,
                err=True,
            )
        typer.secho(
            "Remediation: run 'ocframework init --force' to generate the missing .env.",
            fg=typer.colors.YELLOW,
            err=True,
        )
        raise typer.Exit(1)

    searched = ", ".join(
        spec.config_dirname
        for spec in sorted(SUPPORTED_TOOLS.values(), key=lambda s: s.name)
    )
    typer.secho(
        f"Error: no framework config directory found in this repository "
        f"(searched {searched}).",
        fg=typer.colors.RED,
        err=True,
    )
    typer.secho(
        "Remediation: run 'ocframework init' to create one.",
        fg=typer.colors.YELLOW,
        err=True,
    )
    raise typer.Exit(1)


def _check_framework_repo() -> Optional[str]:
    """Check if the framework repo is installed.

    Returns None when installed from a git clone, error message otherwise.
    """
    settings = discover_global_settings()

    if not settings.framework_repo_path:
        return (
            "Framework repository not found.\n"
            "The framework must be installed as an editable package from a git clone:\n"
            "  pipx install -e <path-to-framework-git-clone>"
        )

    return None


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    version: bool = typer.Option(
        False,
        "--version",
        "-v",
        help="Print version information and exit",
    ),
) -> None:
    """OpenCode Framework - AI coding agent attachment framework."""
    error = _check_framework_repo()
    if error:
        typer.secho(
            "Error: Framework repository is invalid.", fg=typer.colors.RED, err=True
        )
        typer.echo(error, err=True)
        raise typer.Exit(1)

    if version or ctx.invoked_subcommand is None:
        _print_version_info()
        raise typer.Exit()


@app.command()
def init(
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Force regeneration by backing up the existing config worktree",
    ),
    tool: Optional[str] = typer.Option(
        None,
        "--tool",
        help="Agent CLI tool to configure (opencode | qwen); prompted when omitted",
    ),
) -> None:
    """Initialize the framework in a Git repository.

    Creates the selected agent CLI tool's config worktree (.opencode/ for
    opencode, .qwen/ for qwen) with the framework configuration.
    """
    repo_path = Path.cwd()

    if tool is None:
        tool = typer.prompt(
            "\nAgent CLI tool (opencode | qwen)",
            default=DEFAULT_TOOL,
            type=str,
        )
    spec = resolve_tool_or_exit(tool)

    typer.echo("Running preflight checks...")
    result = run_preflight_checks(repo_path, force=force, agent_tool=spec.name)

    if not result.success:
        typer.secho(f"Preflight failed: {result.error}", fg=typer.colors.RED, err=True)
        if result.remediation:
            typer.secho(f"Remediation: {result.remediation}", fg=typer.colors.YELLOW)
        raise typer.Exit(1)

    typer.secho("Preflight checks passed.", fg=typer.colors.GREEN)

    config_dir = repo_path / spec.config_dirname
    backup_path: Optional[Path] = None

    if force and config_dir.exists():
        typer.echo(f"Backing up existing {spec.config_dirname}/...")
        if is_worktree(config_dir):
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            backup_path = repo_path / f"{spec.config_dirname}.backup-{timestamp}"

            shutil.copytree(config_dir, backup_path, symlinks=True)
            typer.echo(f"Backup created at: {backup_path}")

            if not remove_worktree(config_dir, cwd=repo_path):
                typer.secho(
                    "Failed to remove existing worktree",
                    fg=typer.colors.RED,
                    err=True,
                )
                raise typer.Exit(1)
        else:
            backup_path = GenerationOrchestrator.backup_existing_config_dir(
                repo_path, spec.name
            )
            if backup_path:
                typer.echo(f"Backup created at: {backup_path}")

    typer.echo("Running setup wizard...")
    wizard_result = run_wizard(repo_path, result, agent_tool=spec.name)

    if wizard_result.create_global_config:
        global_spec = resolve_tool_or_exit(wizard_result.agent_tool)
        global_config_dir = expected_global_path(global_spec)
        typer.echo(f"Creating global config directory: {global_config_dir}")
        try:
            global_config_dir.mkdir(parents=True, exist_ok=True)
            typer.secho("Global config directory created.", fg=typer.colors.GREEN)
        except OSError as e:
            typer.secho(
                f"Failed to create global config directory: {e}",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(1) from e

    typer.echo(f"Setting up worktree on branch '{wizard_result.branch_name}'...")
    worktree_result = setup_opencode_worktree(
        repo_root=repo_path,
        branch_name=wizard_result.branch_name,
        config_dir=config_dir,
    )

    if not worktree_result.success:
        typer.secho(
            f"Failed to create worktree: {worktree_result.error}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)

    typer.echo(f"Generating {spec.config_dirname}/ directory...")
    orchestrator = GenerationOrchestrator()
    orchestrator.generate(repo_path, wizard_result)

    commands = DocumentationGenerator._get_launch_commands(wizard_result.agent_tool)

    typer.secho("Initialization complete!", fg=typer.colors.GREEN)
    typer.echo("\nCommands:")
    typer.echo(f"  Launch: {commands['launch']}")
    typer.echo(f"  Debug:  {commands['debug']}")
    typer.echo(f"  Shell:  {commands['shell']}")


def _parse_image_id_from_build_output(output: str) -> Optional[str]:
    """Parse image ID from devcontainer build output.

    Devcontainer build outputs JSON lines. We look for the image ID in the output.
    """
    for line in output.strip().split("\n"):
        line = line.strip()
        if not line:
            continue
        try:
            data = json.loads(line)
            if "outcome" in data and "containerId" in data:
                container_id = data["containerId"]
                try:
                    inspect_result = subprocess.run(
                        [
                            "docker",
                            "inspect",
                            "--format={{.Config.Image}}",
                            container_id,
                        ],
                        capture_output=True,
                        text=True,
                    )
                finally:
                    subprocess.run(["docker", "rm", "-f", container_id])
                return inspect_result.stdout.strip()

        except json.JSONDecodeError:
            continue

    sha256_pattern = re.compile(r"(sha256:[a-f0-9]{64}|[a-f0-9]{12,64})")
    match = sha256_pattern.search(output)
    if match:
        return match.group(1)

    return None


def _extract_server_arg(
    extra_args: List[str],
) -> Tuple[Optional[str], List[str]]:
    """Extract --server / --server=VALUE / --server VALUE from extra args.

    Consumes the first --server occurrence:
    - ``--server=VALUE`` → server="VALUE" (may be "")
    - ``--server`` followed by an all-digit token of length 1-5 →
      server=<that token>, both consumed
    - ``--server`` otherwise (end of list, or next token is non-numeric like
      ``--rebuild`` or ``serve``) → server=""
    - No ``--server`` present → server=None, list unchanged

    Only the first --server occurrence is consumed.

    Args:
        extra_args: Pass-through args from ``ctx.args``.

    Returns:
        Tuple of (server_value, remaining_args_with_server_tokens_removed).
    """
    remaining: List[str] = []
    server: Optional[str] = None
    i = 0
    n = len(extra_args)
    while i < n:
        token = extra_args[i]
        if server is None and token == "--server":
            if (
                i + 1 < n
                and extra_args[i + 1].isdigit()
                and 1 <= len(extra_args[i + 1]) <= 5
            ):
                server = extra_args[i + 1]
                i += 2
            else:
                server = ""
                i += 1
        elif server is None and token.startswith("--server="):
            server = token[len("--server=") :]
            i += 1
        else:
            remaining.append(token)
            i += 1
    return server, remaining


def _extract_host_ports(port_mappings: List[str]) -> List[int]:
    """Return the host-side port number from each 'HOST:CONTAINER[/proto]' mapping.

    Silently skips mappings whose host part is not a plain integer (e.g. named
    targets or ranges) — Docker will surface any real conflict for those.

    Args:
        port_mappings: Strings as returned by ``ComposeGenerator.detect_ports``,
            e.g. ``["8080:8080", "8443:443/tcp"]``.

    Returns:
        List of integer host ports.
    """
    hosts: List[int] = []
    for mapping in port_mappings:
        left = mapping.split(":", 1)[0]
        try:
            hosts.append(int(left))
        except ValueError:
            continue
    return hosts


def _resolve_server_port(
    server: str,
    extra_args: List[str],
    spec: ToolSpec,
    reserved_host_ports: Optional[List[int]] = None,
) -> int:
    """Resolve the host port for ``--server``.

    Args:
        server: Raw value of the ``--server`` option (empty string for bare
            ``--server``, otherwise a numeric port string).
        extra_args: Pass-through args destined for the agent inside the
            container. Used to detect a conflicting explicit ``serve``.
        spec: ToolSpec of the configured agent (for port and wording).
        reserved_host_ports: Host ports already claimed by wizard-configured
            compose mappings. Bare ``--server`` skips these when auto-picking;
            explicit ``--server=N`` fails fast if N is in the list.

    Returns:
        Resolved host port number.

    Raises:
        typer.Exit: On conflict, invalid port, or no free port available.
    """
    if any(a == "serve" for a in extra_args):
        typer.secho(
            "Error: --server conflicts with 'serve' in pass-through args.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)

    if server == "":
        try:
            host_port = find_free_port(
                SERVER_HOST_PORT_MIN,
                SERVER_HOST_PORT_MAX,
                reserved=reserved_host_ports,
            )
        except PortAllocationError as e:
            typer.secho(f"Error: {e.message}", fg=typer.colors.RED, err=True)
            typer.secho(
                f"Remediation: {e.remediation}", fg=typer.colors.YELLOW, err=True
            )
            raise typer.Exit(1) from None
        typer.echo(f"Auto-assigned server port: {host_port}")
    else:
        try:
            host_port = int(server)
            if not (1 <= host_port <= 65535):
                raise ValueError
        except ValueError:
            typer.secho(
                f"Error: invalid --server port: {server!r}",
                fg=typer.colors.RED,
                err=True,
            )
            raise typer.Exit(1) from None

        if reserved_host_ports and host_port in reserved_host_ports:
            typer.secho(
                f"Error: --server host port {host_port} conflicts with a "
                f"compose port mapping.",
                fg=typer.colors.RED,
                err=True,
            )
            typer.secho(
                "Remediation: pass --server=<other-port> or edit "
                ".opencode/docker-compose.yaml to free the port.",
                fg=typer.colors.YELLOW,
                err=True,
            )
            raise typer.Exit(1) from None

    typer.echo(f"{spec.name} serve will be available at http://127.0.0.1:{host_port}")
    return host_port


def _ensure_server_token(final_env: Dict[str, str], spec: ToolSpec) -> None:
    """Auto-generate the serve token when the tool requires one.

    The token is injected into the container environment via
    ``docker compose run --env`` and never written to disk; a
    user-provided value (env file or ``-e``) always wins.

    Args:
        final_env: Merged environment; updated in place.
        spec: ToolSpec of the configured agent.
    """
    if not spec.serve.token_required:
        return
    if final_env.get(spec.serve.token_env):
        return
    token = secrets.token_hex(32)
    final_env[spec.serve.token_env] = token
    typer.echo(f"Web Shell token ({spec.serve.token_env}): {token}")


def _extract_container_name(compose_path: Path) -> Optional[str]:
    """Extract container_name from docker-compose.yaml.

    Args:
        compose_path: Path to docker-compose.yaml

    Returns:
        Container name if found, None otherwise
    """
    content = compose_path.read_text()
    match = re.search(r"^\s*container_name:\s*(.+)$", content, re.MULTILINE)
    if match:
        return match.group(1).strip()
    return None


def _get_container_status(container_name: str, subprocess_env: dict) -> Optional[str]:
    """Get the status of a container.

    Args:
        container_name: Name of the container
        subprocess_env: Environment variables for subprocess

    Returns:
        Container status (e.g., 'running', 'exited', 'created') if exists,
        None otherwise
    """
    try:
        result = subprocess.run(
            ["docker", "inspect", "--format", "{{.State.Status}}", container_name],
            env=subprocess_env,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            status = result.stdout.strip()
            return status if status else None
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    return None


def _get_container_ports(container_name: str, subprocess_env: dict) -> Optional[str]:
    """Return the port mapping lines for a running container.

    Args:
        container_name: Name of the container
        subprocess_env: Environment variables for subprocess

    Returns:
        Raw ``docker port`` output (e.g. ``"4096/tcp -> 0.0.0.0:4096"``),
        or None when the container has no published ports or the command fails.
    """
    try:
        result = subprocess.run(
            ["docker", "port", container_name],
            env=subprocess_env,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            output = result.stdout.strip()
            return output if output else None
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    return None


def _remove_container(container_name: str, subprocess_env: dict) -> bool:
    """Force-remove a container.

    Args:
        container_name: Name of the container
        subprocess_env: Environment variables for subprocess

    Returns:
        True if removal succeeded, False otherwise
    """
    try:
        result = subprocess.run(
            ["docker", "rm", "-f", container_name],
            env=subprocess_env,
            capture_output=True,
            text=True,
            timeout=30,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def _build_image(config_dir: Path, repo_root: Path, subprocess_env: dict) -> str:
    # devcontainer build does not call initializeCommand https://github.com/devcontainers/cli/issues/190
    build_cmd = [
        "devcontainer",
        "up",
        "--remove-existing-container",
        "--config",
        str(config_dir / "devcontainer.json"),
        "--workspace-folder",
        str(repo_root),
    ]

    process = subprocess.Popen(
        build_cmd,
        env=subprocess_env,
        cwd=repo_root,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    output_lines = []
    for line in process.stdout:  # type: ignore[union-attr]
        typer.echo(line, nl=False)
        output_lines.append(line)

    process.wait()
    output = "".join(output_lines)

    if process.returncode != 0:
        typer.secho("Failed to build devcontainer image", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)

    image_id = _parse_image_id_from_build_output(output)

    if not image_id:
        typer.secho(
            "Could not parse image ID from build output", fg=typer.colors.RED, err=True
        )
        raise typer.Exit(1)

    typer.echo(f"Built image: {image_id}")
    return image_id


@app.command(
    context_settings={"allow_extra_args": True, "ignore_unknown_options": True}
)
def launch(
    ctx: typer.Context,
    docker_context: str = typer.Option(
        "rootless",
        "--docker-context",
        help="Docker context to use",
    ),
    env_file: Optional[Path] = typer.Option(  # noqa: B008
        None,
        "--env-file",
        help="Path to environment override file (.env format)",
        exists=True,
        file_okay=True,
        dir_okay=False,
    ),
    env_vars: Optional[List[str]] = typer.Option(  # noqa: B008
        None,
        "-e",
        "--env",
        help="Set environment variable (KEY=VALUE). Can be used multiple times.",
    ),
    tool: Optional[str] = typer.Option(
        None,
        "--tool",
        help="Agent tool to launch (opencode | qwen); auto-detected when omitted",
    ),
    rebuild: bool = typer.Option(
        False,
        "--rebuild",
        help="Force rebuild of the devcontainer image",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Remove any existing container and cached image ID, forcing a fresh build",
    ),
) -> None:
    """Launch the configured agent (opencode or qwen) in a container.

    Builds the devcontainer image (if needed) and runs the agent using
    docker compose. The config worktree is chosen by --tool when given,
    else by an OCF_AGENT_TOOL override from -e/--env or --env-file, else
    by auto-detecting the single valid config directory (a prompt is
    shown when several exist).

    Environment variables are loaded with precedence (lowest to highest):
    1. Global env file (~/.config/opencode/.env for opencode, ~/.qwen/.env
       for qwen; auto-loaded if present)
    2. Base <config-dir>/.env file
    3. Override file (--env-file)
    4. Command-line variables (-e KEY=VALUE)

    Supports:
    - Variable interpolation: $VAR, ${VAR}, ${VAR:-default}
    - Export statements: export KEY=VALUE
    - Comments: # comment
    - Quoted values: KEY="value with spaces"

    DOCKER_CONTEXT is set to 'rootless' by default. Use --docker-context to override.

    Examples:
        ocframework launch
        ocframework launch --tool qwen
        ocframework launch --rebuild
        ocframework launch --env-file prod.env
        ocframework launch -e API_KEY=$HOME/.key -e DEBUG=true
        ocframework launch --server
        ocframework launch --server=5000
    """
    cwd = Path.cwd()

    repo_root = get_repo_root(cwd)
    if repo_root is None:
        typer.secho(
            "Error: Current directory is not inside a Git working tree",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)

    if repo_root != cwd.resolve():
        typer.secho(
            "Error: Current directory is not the repository root. "
            f"Run from: {repo_root}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)

    config_dir, spec = _select_launch_target(repo_root, tool, env_file, env_vars)

    valid, error = validate_runtime_context(cwd, spec.config_dirname)
    if not valid:
        typer.secho(f"Error: {error}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)

    env_path = config_dir / ".env"
    global_env_path = expected_global_env_path(spec)
    warnings: List[str] = []

    try:
        final_env = load_env_with_overrides(
            base_env_path=env_path,
            override_env_path=env_file,
            cli_env_vars=env_vars,
            global_env_path=global_env_path,
            warnings=warnings,
        )
    except EnvError as e:
        typer.secho(f"Error: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1) from None
    except FileNotFoundError as e:
        typer.secho(f"Error: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1) from None
    except Exception as e:
        typer.secho(f"Error loading environment: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1) from None

    # Print any warnings (e.g., global env file failed to parse)
    for warning in warnings:
        typer.secho(f"Warning: {warning}", fg=typer.colors.YELLOW)

    subprocess_env = build_docker_env(final_env, docker_context)

    compose_path = config_dir / "docker-compose.yaml"

    if not compose_path.exists():
        typer.secho(
            "Error: docker-compose.yaml not found. Run 'ocframework init' first.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)

    image_id = None

    if force and remove_image_id(config_dir):
        typer.echo("Removed cached image ID; image will be rebuilt.")

    if rebuild:
        if update_features(config_dir, repo_root.name, spec.name):
            typer.echo("Feature configuration changed; rebuilding image...")
        else:
            typer.echo("Building devcontainer image (--rebuild specified)...")
        image_id = _build_image(config_dir, repo_root, subprocess_env)
    else:
        image_id = load_image_id(config_dir)
        if image_id:
            typer.echo(f"Using existing image: {image_id}")
        else:
            typer.echo("Building devcontainer image (no cached image ID found)...")
            image_id = _build_image(config_dir, repo_root, subprocess_env)

    save_image_id(config_dir, image_id)

    subprocess_env["OCF_IMAGE_ID"] = image_id
    subprocess_env["PWD"] = str(repo_root)

    detected_ports = ComposeGenerator.detect_ports(compose_path.read_text())
    reserved_host_ports = _extract_host_ports(detected_ports)

    server, remaining_args = _extract_server_arg(ctx.args)
    ctx.args[:] = remaining_args

    server_host_port: Optional[int] = None
    if server is not None:
        server_host_port = _resolve_server_port(
            server, ctx.args, spec, reserved_host_ports=reserved_host_ports
        )
        _ensure_server_token(final_env, spec)

    container_name = _extract_container_name(compose_path)

    # Handle existing container: attach if running, otherwise remove
    if container_name:
        status = _get_container_status(container_name, subprocess_env)
        if status == "running" and not force:
            typer.echo(f"Container '{container_name}' is already running. Attaching...")
            ports = _get_container_ports(container_name, subprocess_env)
            if ports:
                typer.echo("Port mappings:")
                for line in ports.splitlines():
                    typer.echo(f"  {line}")
            attach_result = subprocess.run(
                ["docker", "attach", container_name],
                env=subprocess_env,
                cwd=repo_root,
            )
            attach_rc = attach_result.returncode
            if attach_rc < 128 and attach_rc != 0:
                # Attach failure (not a signal). 128+N = killed by signal N
                # (e.g. 130 = SIGINT/Ctrl+C), which is an intentional interrupt,
                # not a failure.
                typer.secho(
                    f"Failed to attach to container '{container_name}' "
                    f"(exit code {attach_rc}).",
                    fg=typer.colors.RED,
                    err=True,
                )
                typer.secho(
                    "Run 'ocframework launch --force' to remove the running container "
                    "and start a new one.",
                    fg=typer.colors.YELLOW,
                    err=True,
                )
            raise typer.Exit(attach_rc)
        elif status is not None:
            # Stopped container (can't attach) or --force on any existing
            prefix = "Force-removing" if force else "Found stopped"
            typer.secho(
                f"{prefix} container '{container_name}' "
                f"(status: {status}). Removing...",
                fg=typer.colors.YELLOW,
            )
            if _remove_container(container_name, subprocess_env):
                typer.secho(
                    f"Removed container '{container_name}'.", fg=typer.colors.GREEN
                )
            else:
                typer.secho(
                    f"Failed to remove container '{container_name}'; continuing.",
                    fg=typer.colors.YELLOW,
                    err=True,
                )

    typer.echo(f"Launching {spec.name}...")

    args = ctx.args

    run_cmd = [
        "docker",
        "compose",
        "-f",
        str(compose_path),
        "run",
        "--rm",
    ]

    if server_host_port is not None:
        # --service-ports and --publish are mutually exclusive in
        # `docker compose run`, so when --server is active we explicitly
        # republish every wizard-declared port instead.
        for mapping in detected_ports:
            run_cmd.extend(["--publish", mapping])
        run_cmd.extend(["--publish", f"{server_host_port}:{spec.serve.port}"])
    elif detected_ports:
        run_cmd.append("--service-ports")

    if container_name:
        run_cmd.extend(["--name", container_name])

    for key, value in final_env.items():
        run_cmd.extend(["--env", f"{key}={value}"])

    run_cmd.append(spec.binary)
    if server_host_port is not None:
        run_cmd.extend(spec.serve.serve_args)
    run_cmd.extend(args)

    result = None
    try:
        result = subprocess.run(run_cmd, env=subprocess_env, cwd=repo_root)
        raise typer.Exit(result.returncode)
    except KeyboardInterrupt:
        # Cleanup: stop the container if it's still running
        typer.echo("\nInterrupted. Cleaning up container...", err=True)
        if container_name:
            cleanup_cmd = ["docker", "rm", "-f", container_name]
            subprocess.run(cleanup_cmd, env=subprocess_env, capture_output=True)
        # Also run docker compose down to clean up any remaining resources
        down_cmd = [
            "docker",
            "compose",
            "-f",
            str(compose_path),
            "down",
            "--remove-orphans",
        ]
        subprocess.run(down_cmd, env=subprocess_env, capture_output=True)
        typer.secho(
            "Cleanup complete. Press Ctrl+C again to force exit.",
            fg=typer.colors.YELLOW,
            err=True,
        )
        raise typer.Exit(130) from None  # 130 is standard exit code for SIGINT
    except Exception:
        # Re-raise any other exception
        raise


if __name__ == "__main__":
    app()
