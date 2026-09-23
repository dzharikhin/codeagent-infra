"""CLI entrypoint for ocframework."""

import json
import os
import re
import secrets
import shutil
import signal
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import IO, Any, Dict, List, NoReturn, Optional, Tuple

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
    expected_global_auth_path,
    expected_global_env_path,
    expected_global_path,
)
from opencode_framework.agent.registry import (
    DEFAULT_TOOL,
    DSH_TOOL_SPEC,
    OPENCODE_TOOL_SPEC,
    QWEN_TOOL_SPEC,
    SUPPORTED_TOOLS,
    ToolSpec,
)
from opencode_framework.config import discover_global_settings
from opencode_framework.exceptions import PortAllocationError
from opencode_framework.generators.documentation import DocumentationGenerator
from opencode_framework.generators.orchestrator import GenerationOrchestrator
from opencode_framework.git_ops import (
    get_current_branch,
    get_repo_root,
    is_worktree,
    remove_worktree,
    setup_config_worktree,
)
from opencode_framework.preflight import run_preflight_checks
from opencode_framework.sandbox.compose import ComposeGenerator
from opencode_framework.sandbox.features import is_interactive, update_features
from opencode_framework.sandbox.net import (
    SERVER_HOST_PORT_MAX,
    SERVER_HOST_PORT_MIN,
    find_free_port,
)
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

    opencode_layer = discover_global_layer(OPENCODE_TOOL_SPEC)
    typer.echo(f"global config found: {opencode_layer.global_found}")
    if opencode_layer.global_found:
        typer.echo(f"global config path: {opencode_layer.global_path}")
    else:
        expected_config = expected_global_path(OPENCODE_TOOL_SPEC)
        typer.echo(f"expected global config path: {expected_config}")
    typer.echo(f"global auth.json found: {opencode_layer.auth_found}")
    if opencode_layer.auth_found:
        typer.echo(f"global auth.json path: {opencode_layer.auth_path}")
    else:
        expected_auth = expected_global_auth_path(OPENCODE_TOOL_SPEC)
        typer.echo(f"expected global auth.json path: {expected_auth}")

    qwen_layer = discover_global_layer(QWEN_TOOL_SPEC)
    typer.echo(f"qwen global settings found: {qwen_layer.global_found}")
    if qwen_layer.global_found:
        typer.echo(f"qwen global settings path: {qwen_layer.global_path}")
    else:
        expected_qwen_path = expected_global_path(QWEN_TOOL_SPEC)
        typer.echo(f"expected qwen global settings path: {expected_qwen_path}")

    dsh_layer = discover_global_layer(DSH_TOOL_SPEC)
    typer.echo(f"dsh global settings found: {dsh_layer.global_found}")
    if dsh_layer.global_found:
        typer.echo(f"dsh global settings path: {dsh_layer.global_path}")
    else:
        expected_dsh_path = expected_global_path(DSH_TOOL_SPEC)
        typer.echo(f"expected dsh global settings path: {expected_dsh_path}")
    typer.echo(f"dsh credentials found: {dsh_layer.auth_found}")
    if dsh_layer.auth_found:
        typer.echo(f"dsh credentials path: {dsh_layer.auth_path}")
    else:
        expected_dsh_auth = expected_global_auth_path(DSH_TOOL_SPEC)
        typer.echo(f"expected dsh credentials path: {expected_dsh_auth}")


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
    env_override = _peek_env_agent_tool(env_file, env_vars)

    requested: Optional[ToolSpec] = None
    if tool is not None:
        requested = resolve_tool_or_exit(tool)
    elif env_override:
        requested = resolve_tool_or_exit(
            env_override,
            hint=f"Fix {AGENT_TOOL_KEY} in -e/--env or the --env-file override.",
        )

    if requested is not None:
        loc = _require_location(repo_root, locations, requested)
        if tool is not None and env_override and env_override != requested.name:
            typer.secho(
                f"Warning: {AGENT_TOOL_KEY}={env_override!r} from -e/--env or "
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
                "Remediation: pass --tool (opencode | qwen | dsh) to choose one.",
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
        help=(
            "Agent CLI tool to configure (opencode | qwen | dsh); prompted when omitted"
        ),
    ),
) -> None:
    """Initialize the framework in a Git repository.

    Creates the selected agent CLI tool's config worktree (.opencode/ for
    opencode, .qwen/ for qwen, .dsh/ for dsh) with the framework
    configuration.
    """
    repo_path = Path.cwd()

    if tool is None:
        tool = typer.prompt(
            "\nAgent CLI tool (opencode | qwen | dsh)",
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
    wizard_result = run_wizard(repo_path, spec.name)

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
    worktree_result = setup_config_worktree(
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

    commands = DocumentationGenerator.get_launch_commands(wizard_result.agent_tool)

    typer.secho("Initialization complete!", fg=typer.colors.GREEN)
    typer.echo("\nCommands:")
    typer.echo(f"  Launch: {commands['launch']}")
    typer.echo(f"  Debug:  {commands['debug']}")
    typer.echo(f"  Shell:  {commands['shell']}")


def _verify_build_output(output: str) -> bool:
    """Check that ``devcontainer up`` produced a parseable build result.

    Devcontainer build output is JSON lines; the line carrying an
    ``outcome`` also names a throwaway ``containerId``. That leftover
    container is removed here (compose launches its own), and the
    success condition is that its image reference resolved to a
    non-empty name. As a fallback, a raw image ID is regex-searched in
    the output.
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
                return bool(inspect_result.stdout.strip())

        except json.JSONDecodeError:
            continue

    sha256_pattern = re.compile(r"(sha256:[a-f0-9]{64}|[a-f0-9]{12,64})")
    return sha256_pattern.search(output) is not None


_IMAGE_NAME_INVALID = re.compile(r"[^a-z0-9._-]+")


def _per_tool_image_tag(repo_name: str, agent_tool: str) -> str:
    """Build the per-tool image tag ``ocf-<repo>-<tool>:latest``.

    Docker image names must be lowercase, so the repo name is slugified
    into a valid image-name component (``[a-z0-9._-]`` with alphanumeric
    boundaries).

    Args:
        repo_name: Repository directory name.
        agent_tool: Agent tool name ("opencode" | "qwen" | "dsh").

    Returns:
        Image tag such as ``ocf-my-repo-opencode:latest``.
    """
    slug = _IMAGE_NAME_INVALID.sub("-", repo_name.lower())
    slug = re.sub(r"^[^a-z0-9]+|[^a-z0-9]+$", "", slug)
    return f"ocf-{slug or 'repo'}-{agent_tool}:latest"


def _parse_image_name_from_build_json(output: str) -> Optional[str]:
    """Parse the image name from ``devcontainer build`` JSON output.

    The build command emits one JSON object per line; the success line
    carries ``imageName`` (a string, or a list of strings when
    ``--image-name`` was repeatable).
    """
    for line in output.strip().split("\n"):
        line = line.strip()
        if not line:
            continue
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(data, dict) or data.get("outcome") != "success":
            continue
        image_name = data.get("imageName")
        if isinstance(image_name, list):
            return next((n for n in image_name if isinstance(n, str) and n), None)
        if isinstance(image_name, str) and image_name:
            return image_name
    return None


def _docker(
    args: List[str],
    env: Optional[dict] = None,
    timeout: int = 30,
) -> Optional[subprocess.CompletedProcess]:
    """Run a docker command with captured output.

    Returns None when the command times out or docker is unavailable.
    """
    try:
        return subprocess.run(
            ["docker"] + args,
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return None


def _capture_tagged_image_id(tag: str, subprocess_env: dict) -> Optional[str]:
    """Return the image ID currently carrying ``tag``, or None."""
    result = _docker(
        ["images", "--filter", f"reference={tag}", "--format", "{{.ID}}"],
        env=subprocess_env,
    )
    if result is None or result.returncode != 0:
        return None
    ids = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    return ids[0] if ids else None


def _inspect_image_id(reference: str, subprocess_env: dict) -> Optional[str]:
    """Return the image ID behind ``reference``, or None."""
    result = _docker(
        ["image", "inspect", "--format", "{{.Id}}", reference],
        env=subprocess_env,
    )
    if result is None or result.returncode != 0:
        return None
    return result.stdout.strip()


def _remove_image(image_id: str, subprocess_env: dict) -> bool:
    """Best-effort removal of a previous (now dangling) image."""
    result = _docker(["rmi", image_id], env=subprocess_env)
    return result is not None and result.returncode == 0


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


_ACP_POSTFIX_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.-]*$")


def _is_valid_acp_postfix(postfix: str) -> bool:
    """Check the container-name postfix passed to ``--acp``.

    The postfix becomes part of a Docker container name, which only
    accepts ``[a-zA-Z0-9][a-zA-Z0-9_.-]*``.

    Args:
        postfix: Value passed via ``--acp``.

    Returns:
        True when the postfix is safe to append to a container name.
    """
    return bool(_ACP_POSTFIX_RE.match(postfix))


def _get_container_status(container_name: str, subprocess_env: dict) -> Optional[str]:
    """Get the status of a container.

    Args:
        container_name: Name of the container
        subprocess_env: Environment variables for subprocess

    Returns:
        Container status (e.g., 'running', 'exited', 'created') if exists,
        None otherwise
    """
    result = _docker(
        ["inspect", "--format", "{{.State.Status}}", container_name],
        env=subprocess_env,
    )
    if result is not None and result.returncode == 0:
        status = result.stdout.strip()
        return status if status else None
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
    result = _docker(["port", container_name], env=subprocess_env)
    if result is not None and result.returncode == 0:
        output = result.stdout.strip()
        return output if output else None
    return None


def _remove_container(container_name: str, subprocess_env: dict) -> bool:
    """Force-remove a container.

    Args:
        container_name: Name of the container
        subprocess_env: Environment variables for subprocess

    Returns:
        True if removal succeeded, False otherwise
    """
    result = _docker(["rm", "-f", container_name], env=subprocess_env)
    return result is not None and result.returncode == 0


def _build_image(
    config_dir: Path, repo_root: Path, subprocess_env: dict, agent_tool: str
) -> str:
    """Build the devcontainer image and tag it per tool.

    Two-step flow:
    1. ``devcontainer up`` — runs initializeCommand (Dockerfile generation)
       and builds. `devcontainer build` does not call initializeCommand
       https://github.com/devcontainers/cli/issues/190 — so `up` stays
       the first step.
    2. ``devcontainer build --image-name`` — replays from layer cache and
       applies the per-tool tag, so opencode, qwen and dsh never collide on
       the workspace-derived vsc-... image name.

    Args:
        config_dir: Agent tool's config worktree directory.
        repo_root: Repository root (workspace folder).
        subprocess_env: Environment variables for subprocess.
        agent_tool: Agent tool name ("opencode" | "qwen" | "dsh").

    Returns:
        The per-tool image tag (persisted as OCF_IMAGE_ID).
    """
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

    if not _verify_build_output(output):
        typer.secho(
            "Could not parse image ID from build output", fg=typer.colors.RED, err=True
        )
        raise typer.Exit(1)

    tag = _per_tool_image_tag(repo_root.name, agent_tool)
    old_image_id = _capture_tagged_image_id(tag, subprocess_env)

    tag_cmd = [
        "devcontainer",
        "build",
        "--config",
        str(config_dir / "devcontainer.json"),
        "--workspace-folder",
        str(repo_root),
        "--image-name",
        tag,
    ]

    tag_process = subprocess.Popen(
        tag_cmd,
        env=subprocess_env,
        cwd=repo_root,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    tag_lines = []
    for line in tag_process.stdout:  # type: ignore[union-attr]
        typer.echo(line, nl=False)
        tag_lines.append(line)

    tag_process.wait()

    if tag_process.returncode != 0:
        typer.secho("Failed to tag devcontainer image", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)

    tag_output = "".join(tag_lines)
    tagged = _parse_image_name_from_build_json(tag_output) or tag

    # Garbage control: drop the previous image the tag pointed at.
    new_image_id = _inspect_image_id(tagged, subprocess_env)
    if old_image_id and new_image_id and old_image_id != new_image_id:
        if _remove_image(old_image_id, subprocess_env):
            typer.echo(f"Removed previous image: {old_image_id}")

    typer.echo(f"Built image: {tagged}")
    return tagged


def _resolve_local_repo_root(
    final_env: Dict[str, str],
    repo_root: Path,
    global_env_path: Path,
) -> Tuple[str, Optional[str]]:
    """Resolve OCF_LOCAL_REPO_ROOT from the env layers.

    A directly set ``OCF_LOCAL_REPO_ROOT`` (any env layer) wins;
    otherwise the identity ``${OCF_LOCAL_PROJECTS_DIR}/${repo_name}`` is
    used. The projects directory comes from the env layers (global .env <
    project .env < overrides < CLI); ``~`` is expanded. When unset or
    empty, falls back to the repository's parent directory — consistent
    with the compose ``${PWD}`` fallback for direct compose runs.

    Args:
        final_env: Merged environment from the config dir's env layers
        repo_root: Git-verified repository root
        global_env_path: Host path of the tool's global .env file,
            named in the fallback note

    Returns:
        (repo_root_str, fallback_note). The note is None when the value
        was set directly or derived from a configured projects dir;
        otherwise it is a console message naming the global env file and
        the line to add.
    """
    direct_raw = final_env.get("OCF_LOCAL_REPO_ROOT", "").strip()
    if direct_raw:
        return str(Path(direct_raw).expanduser()), None

    repo_name = repo_root.name
    projects_dir_raw = final_env.get("OCF_LOCAL_PROJECTS_DIR", "").strip()
    if not projects_dir_raw:
        projects_dir = repo_root.parent
        note = (
            "OCF_LOCAL_PROJECTS_DIR not set; deriving project location from "
            f"the repository path ({projects_dir}). Add "
            "'OCF_LOCAL_PROJECTS_DIR=<your-projects-dir>' to "
            f"{global_env_path} to pin where projects live."
        )
    else:
        projects_dir = Path(projects_dir_raw).expanduser()
        note = None

    return str(projects_dir / repo_name), note


_ACP_ENVELOPE_PREFIX = b'{"jsonrpc"'


def _acp_redirect_stdout_to_stderr() -> IO[bytes]:
    """Move launch's stdout to stderr and return the real stdout handle.

    In ACP mode the editor consumes launch's stdout as the JSON-RPC
    transport, so every byte of launch chatter must move to stderr. The
    redirection happens at the file-descriptor level (``fd 1`` → ``fd 2``),
    which also captures stream caching inside click/typer. The returned
    binary handle is a dup of the original stdout for the pump's envelope
    writes; ``fd 1`` is never restored (an ACP session ends the process).
    """
    sys.stdout.flush()
    real_stdout = os.fdopen(os.dup(1), "wb")
    os.dup2(2, 1)
    return real_stdout


def _pump_acp_stdout(
    process: subprocess.Popen,
    real_stdout: IO[bytes],
    stderr: IO[bytes],
) -> None:
    """Forward the container's stdout through the ACP envelope filter.

    Lines whose first non-whitespace bytes are ``{"jsonrpc"`` are protocol
    envelopes and go to the editor on the real stdout; every other line
    (docker-init boot lines, plugin banners, agent chatter) is routed to
    stderr. Both streams are flushed per line.

    Args:
        process: The spawned ``docker compose run`` child (bytes stdout).
        real_stdout: Binary handle of launch's original stdout.
        stderr: Binary stderr sink for non-protocol lines.
    """
    assert process.stdout is not None
    while True:
        line = process.stdout.readline()
        if not line:
            break
        if line.lstrip().startswith(_ACP_ENVELOPE_PREFIX):
            real_stdout.write(line)
            real_stdout.flush()
        else:
            stderr.write(line)
            stderr.flush()


def _terminate_acp_child(process: subprocess.Popen) -> None:
    """Terminate the docker child if it is still running."""
    if process.poll() is None:
        process.terminate()


def _compose_cleanup(
    container_name: Optional[str],
    compose_path: Path,
    subprocess_env: dict,
) -> None:
    """Best-effort container cleanup after an interrupted launch.

    Force-removes the run container (when named) and tears down leftover
    compose resources. Shared by the plain-launch and ACP interrupt paths.
    """
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


def _run_acp_session(
    process: subprocess.Popen,
    acp_stdout: IO[bytes],
    compose_path: Path,
    container_name: Optional[str],
    subprocess_env: dict,
) -> NoReturn:
    """Run the ACP stdio session to completion and exit with its code.

    Installs a SIGTERM handler that terminates the docker child (editors
    stop the agent with SIGTERM). A KeyboardInterrupt (Ctrl+C) also
    terminates the child, runs the standard cleanup and exits 130. A child
    killed by a signal exits with the conventional ``128 + N`` code after
    cleanup (SIGTERM → 143).

    Args:
        process: The spawned ``docker compose run`` child.
        acp_stdout: Real stdout handle for the pump's envelope writes.
        compose_path: Path to docker-compose.yaml (for cleanup).
        container_name: Run container name, when the compose file sets one.
        subprocess_env: Environment for the cleanup subprocesses.
    """
    previous_handler: Any = signal.getsignal(signal.SIGTERM)
    signal.signal(
        signal.SIGTERM,
        lambda signum, frame: _terminate_acp_child(process),
    )
    interrupted = False
    try:
        stderr: IO[bytes] = sys.stderr.buffer
        try:
            _pump_acp_stdout(process, acp_stdout, stderr)
        except KeyboardInterrupt:
            interrupted = True
            _terminate_acp_child(process)
    finally:
        signal.signal(signal.SIGTERM, previous_handler)
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
        if not acp_stdout.closed:
            acp_stdout.close()

    if interrupted:
        _compose_cleanup(container_name, compose_path, subprocess_env)
        raise typer.Exit(130) from None

    returncode = process.returncode
    if returncode is not None and returncode < 0:
        _compose_cleanup(container_name, compose_path, subprocess_env)
        raise typer.Exit(128 - returncode)
    raise typer.Exit(returncode)


def _run_acp_launch(
    run_cmd: List[str],
    acp_stdout: IO[bytes],
    subprocess_env: dict,
    repo_root: Path,
    compose_path: Path,
    container_name: Optional[str],
) -> NoReturn:
    """Spawn the ACP container session and run it to completion.

    The docker child inherits stdin and stderr (the editor's pipes) and
    pipes its stdout through the envelope pump. Never returns normally:
    exits with the child's exit code.

    Args:
        run_cmd: Full ``docker compose run`` command line.
        acp_stdout: Real stdout handle for the pump's envelope writes.
        subprocess_env: Environment variables for the child process.
        repo_root: Repository root (child working directory).
        compose_path: Path to docker-compose.yaml (for cleanup).
        container_name: Run container name, when the compose file sets one.
    """
    process = subprocess.Popen(
        run_cmd,
        env=subprocess_env,
        cwd=repo_root,
        stdout=subprocess.PIPE,
    )
    _run_acp_session(process, acp_stdout, compose_path, container_name, subprocess_env)


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
        help=(
            "Agent tool to launch (opencode | qwen | dsh); auto-detected when omitted"
        ),
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
    acp: Optional[str] = typer.Option(
        None,
        "--acp",
        metavar="POSTFIX",
        help=(
            "Run the agent in ACP (Agent Client Protocol) mode: the editor "
            "speaks JSON-RPC to the sandboxed agent over stdio. POSTFIX is "
            "required and is appended to the container name "
            "(ocf_<repo>_<tool>_<postfix>); an existing container with that "
            "name is replaced, so reuse a postfix to restart a session or "
            "pick a unique one per editor instance"
        ),
    ),
) -> None:
    """Launch the configured agent (opencode, qwen or dsh) in a container.

    Builds the devcontainer image (if needed) and runs the agent using
    docker compose. The config worktree is chosen by --tool when given,
    else by an OCF_AGENT_TOOL override from -e/--env or --env-file, else
    by auto-detecting the single valid config directory (a prompt is
    shown when several exist).

    With --acp the agent runs in ACP mode (Agent Client Protocol): launch
    speaks JSON-RPC over stdio so ACP-compatible editors (Zed, JetBrains,
    Neovim) can drive the sandboxed agent. A POSTFIX is required and is
    appended to the container name (ocf_<repo>_<tool>_<postfix>); any
    existing container with that name is removed first, so reusing a
    postfix replaces the previous session. All launch chatter moves to
    stderr; stdout carries only the protocol stream. --server conflicts
    with --acp, and dsh (Web UI based) has no ACP mode.

    Environment variables are loaded with precedence (lowest to highest):
    1. Global env file (~/.config/opencode/.env for opencode, ~/.qwen/.env
       for qwen, ~/.dsh/.env for dsh; auto-loaded if present)
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
        ocframework launch --tool dsh --server
        ocframework launch --rebuild
        ocframework launch --env-file prod.env
        ocframework launch -e API_KEY=$HOME/.key -e DEBUG=true
        ocframework launch --server
        ocframework launch --server=5000
        ocframework launch --tool opencode --acp zed
    """
    # In ACP mode the editor owns stdout (JSON-RPC transport), so move
    # launch's own output to stderr before anything is printed. This also
    # redirects chatter cached inside click/typer because it happens at
    # the file-descriptor level.
    acp_stdout: Optional[IO[bytes]] = None
    if acp:
        acp_stdout = _acp_redirect_stdout_to_stderr()

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

    if acp is not None:
        if not _is_valid_acp_postfix(acp):
            typer.secho(
                f"Error: invalid --acp postfix '{acp}': use letters, digits, "
                "'_', '.' or '-', starting with a letter or digit.",
                fg=typer.colors.RED,
                err=True,
            )
            typer.secho(
                "Remediation: pass a short unique name after --acp, e.g. "
                "'ocframework launch --acp zed'.",
                fg=typer.colors.YELLOW,
                err=True,
            )
            raise typer.Exit(1)
        peek_server, _peek_remaining = _extract_server_arg(list(ctx.args))
        if peek_server is not None:
            typer.secho(
                "Error: --acp and --server are mutually exclusive: --acp "
                "speaks JSON-RPC over stdio, --server serves the Web UI.",
                fg=typer.colors.RED,
                err=True,
            )
            typer.secho(
                "Remediation: use either --acp or --server, not both.",
                fg=typer.colors.YELLOW,
                err=True,
            )
            raise typer.Exit(1)
        if not spec.acp.supported:
            typer.secho(
                f"Error: {spec.name} does not support ACP mode.",
                fg=typer.colors.RED,
                err=True,
            )
            typer.secho(
                f"Remediation: {spec.acp.unsupported_remediation}",
                fg=typer.colors.YELLOW,
                err=True,
            )
            raise typer.Exit(1)

    valid, error = validate_runtime_context(
        cwd, spec.config_dirname, repo_root=repo_root
    )
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

    local_repo_root, fallback_note = _resolve_local_repo_root(
        final_env, repo_root, global_env_path
    )
    if fallback_note:
        typer.secho(f"Note: {fallback_note}", fg=typer.colors.YELLOW)
    direct_set = bool(final_env.get("OCF_LOCAL_REPO_ROOT", "").strip())
    if Path(local_repo_root).resolve() != repo_root.resolve():
        if direct_set:
            typer.secho(
                f"Error: OCF_LOCAL_REPO_ROOT mismatch: {local_repo_root} does "
                f"not match the actual repository root {repo_root}.",
                fg=typer.colors.RED,
                err=True,
            )
            typer.secho(
                "Remediation: fix or remove OCF_LOCAL_REPO_ROOT in the env "
                "files, or override it for this launch with "
                "'ocframework launch -e OCF_LOCAL_REPO_ROOT=<repo-root>'.",
                fg=typer.colors.YELLOW,
                err=True,
            )
        else:
            typer.secho(
                f"Error: OCF_LOCAL_PROJECTS_DIR mismatch: derived project path "
                f"{local_repo_root} does not match the actual repository root "
                f"{repo_root}.",
                fg=typer.colors.RED,
                err=True,
            )
            typer.secho(
                "Remediation: update OCF_LOCAL_PROJECTS_DIR in "
                f"{global_env_path}, or override it for this project with "
                "'ocframework launch -e OCF_LOCAL_PROJECTS_DIR=<projects-dir>'.",
                fg=typer.colors.YELLOW,
                err=True,
            )
        raise typer.Exit(1)
    subprocess_env["OCF_LOCAL_REPO_ROOT"] = local_repo_root

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
        image_id = _build_image(config_dir, repo_root, subprocess_env, spec.name)
    else:
        image_id = load_image_id(config_dir)
        if image_id:
            typer.echo(f"Using existing image: {image_id}")
        else:
            typer.echo("Building devcontainer image (no cached image ID found)...")
            image_id = _build_image(config_dir, repo_root, subprocess_env, spec.name)

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

    if acp:
        # ACP names the run container deterministically: the compose base
        # name plus the editor-provided postfix, so concurrent ACP sessions
        # (different editors) never collide and a reused postfix
        # deterministically replaces the previous session.
        if not container_name:
            typer.secho(
                f"Error: no 'container_name' entry in {compose_path}; "
                "ACP mode needs a deterministic container name.",
                fg=typer.colors.RED,
                err=True,
            )
            typer.secho(
                "Remediation: run 'ocframework init --force --tool "
                f"{spec.name}' to regenerate the compose file.",
                fg=typer.colors.YELLOW,
                err=True,
            )
            raise typer.Exit(1)
        container_name = f"{container_name}_{acp}"

    # Handle existing container: ACP replaces it with a fresh session,
    # plain mode attaches if running, otherwise removes
    if container_name:
        status = _get_container_status(container_name, subprocess_env)
        if acp and status is not None:
            # ACP never attaches: remove any existing container (running
            # or stopped) so the stdio JSON-RPC stream starts with a new
            # session. A removal failure is fatal — a leftover container
            # would surface as a confusing docker name conflict inside
            # the protocol stream.
            typer.secho(
                f"Removing existing container '{container_name}' (status: {status})...",
                fg=typer.colors.YELLOW,
            )
            if not _remove_container(container_name, subprocess_env):
                typer.secho(
                    f"Error: failed to remove container '{container_name}'.",
                    fg=typer.colors.RED,
                    err=True,
                )
                typer.secho(
                    f"Remediation: run 'docker rm -f {container_name}' and retry.",
                    fg=typer.colors.YELLOW,
                    err=True,
                )
                raise typer.Exit(1)
            typer.secho(f"Removed container '{container_name}'.", fg=typer.colors.GREEN)
        elif status == "running" and not force:
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
    elif detected_ports and not acp:
        run_cmd.append("--service-ports")

    if acp:
        # No TTY: the JSON-RPC stdio transport is not interactive, and a
        # pty would corrupt the protocol stream.
        run_cmd.append("-T")

    if container_name:
        run_cmd.extend(["--name", container_name])

    for key, value in final_env.items():
        run_cmd.extend(["--env", f"{key}={value}"])

    run_cmd.append(spec.binary)
    if server_host_port is not None:
        run_cmd.extend(spec.serve.serve_args)
    elif acp:
        run_cmd.extend(spec.acp.args)
    run_cmd.extend(args)

    if acp:
        assert acp_stdout is not None
        _run_acp_launch(
            run_cmd,
            acp_stdout,
            subprocess_env,
            repo_root,
            compose_path,
            container_name,
        )

    try:
        run_result = subprocess.run(run_cmd, env=subprocess_env, cwd=repo_root)
    except KeyboardInterrupt:
        # Cleanup: stop the container if it's still running
        _compose_cleanup(container_name, compose_path, subprocess_env)
        raise typer.Exit(130) from None  # 130 is standard exit code for SIGINT

    raise typer.Exit(run_result.returncode)


if __name__ == "__main__":
    app()
