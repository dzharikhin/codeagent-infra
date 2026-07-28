"""CLI entrypoint for ocframework."""

import json
import re
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple

import typer

from opencode_framework import __version__
from opencode_framework.config import (
    discover_global_settings,
    get_config_root,
    get_framework_validation_error,
    get_local_data_home,
    validate_framework_repo,
)
from opencode_framework.exceptions import PortAllocationError
from opencode_framework.features import update_features
from opencode_framework.generators import GenerationOrchestrator
from opencode_framework.generators.compose import ComposeGenerator
from opencode_framework.generators.documentation import DocumentationGenerator
from opencode_framework.git_ops import (
    is_worktree,
    remove_worktree,
    setup_opencode_worktree,
)
from opencode_framework.net import find_free_port
from opencode_framework.preflight import (
    get_repo_root,
    opencode_directory_exists,
    run_preflight_checks,
)
from opencode_framework.runtime import (
    EnvError,
    build_docker_env,
    load_env_with_overrides,
    load_image_id,
    remove_image_id,
    save_image_id,
    validate_runtime_context,
)
from opencode_framework.wizard import run_wizard

SERVER_CONTAINER_PORT = 4096
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
        valid, missing = validate_framework_repo(Path(framework_path))
        if valid:
            typer.echo(f"framework repo path: {framework_path}")
        else:
            typer.secho(
                f"framework repo path: {framework_path} (INVALID)", fg=typer.colors.RED
            )
            typer.secho(f"  Missing: {', '.join(missing)}", fg=typer.colors.RED)
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


def _check_framework_repo() -> Optional[str]:
    """Check if framework repo is valid.

    Returns None if valid, error message if invalid.
    """
    settings = discover_global_settings()

    if not settings.framework_repo_path:
        return (
            "Framework repository not found.\n"
            "The framework must be installed as an editable package from a git clone:\n"
            "  pipx install -e <path-to-framework-git-clone>"
        )

    valid, missing = validate_framework_repo(Path(settings.framework_repo_path))
    if not valid:
        return get_framework_validation_error(missing, settings.framework_repo_path)

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
        help="Force regeneration by backing up existing .opencode/",
    ),
) -> None:
    """Initialize the framework in a Git repository.

    Creates a .opencode/ directory with configuration for the AI coding agent.
    """
    repo_path = Path.cwd()

    typer.echo("Running preflight checks...")
    result = run_preflight_checks(repo_path, force=force)

    if not result.success:
        typer.secho(f"Preflight failed: {result.error}", fg=typer.colors.RED, err=True)
        if result.remediation:
            typer.secho(f"Remediation: {result.remediation}", fg=typer.colors.YELLOW)
        raise typer.Exit(1)

    typer.secho("Preflight checks passed.", fg=typer.colors.GREEN)

    opencode_dir = repo_path / ".opencode"
    backup_path = None

    if force and opencode_directory_exists(repo_path):
        typer.echo("Backing up existing .opencode/...")
        if is_worktree(opencode_dir):
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            backup_path = repo_path / f".opencode.backup-{timestamp}"

            shutil.copytree(opencode_dir, backup_path, symlinks=True)
            typer.echo(f"Backup created at: {backup_path}")

            if not remove_worktree(opencode_dir, cwd=repo_path):
                typer.secho(
                    "Failed to remove existing worktree",
                    fg=typer.colors.RED,
                    err=True,
                )
                raise typer.Exit(1)
        else:
            backup_path = GenerationOrchestrator.backup_existing_opencode(repo_path)
            if backup_path:
                typer.echo(f"Backup created at: {backup_path}")

    typer.echo("Running setup wizard...")
    wizard_result = run_wizard(repo_path, result)

    if wizard_result.create_global_config:
        config_root = get_config_root()
        global_config_dir = config_root / "opencode"
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
            raise typer.Exit(1)

    typer.echo(f"Setting up worktree on branch '{wizard_result.branch_name}'...")
    worktree_result = setup_opencode_worktree(
        repo_root=repo_path,
        branch_name=wizard_result.branch_name,
        opencode_dir=opencode_dir,
    )

    if not worktree_result.success:
        typer.secho(
            f"Failed to create worktree: {worktree_result.error}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)

    typer.echo("Generating .opencode/ directory...")
    orchestrator = GenerationOrchestrator()
    orchestrator.generate(repo_path, wizard_result)

    commands = DocumentationGenerator._get_launch_commands()

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
    reserved_host_ports: Optional[List[int]] = None,
) -> int:
    """Resolve the host port for ``--server``.

    Args:
        server: Raw value of the ``--server`` option (empty string for bare
            ``--server``, otherwise a numeric port string).
        extra_args: Pass-through args destined for ``opencode`` inside the
            container. Used to detect a conflicting explicit ``serve``.
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

    typer.echo(f"opencode serve will be available at http://127.0.0.1:{host_port}")
    return host_port


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


def _build_image(opencode_dir: Path, repo_root: Path, subprocess_env: dict) -> str:
    # devcontainer build does not call initializeCommand https://github.com/devcontainers/cli/issues/190
    build_cmd = [
        "devcontainer",
        "up",
        "--remove-existing-container",
        "--config",
        str(opencode_dir / "devcontainer.json"),
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
    env_file: Optional[Path] = typer.Option(
        None,
        "--env-file",
        help="Path to environment override file (.env format)",
        exists=True,
        file_okay=True,
        dir_okay=False,
    ),
    env_vars: Optional[List[str]] = typer.Option(
        None,
        "-e",
        "--env",
        help="Set environment variable (KEY=VALUE). Can be used multiple times.",
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
    """Launch the OpenCode agent in a container.

    Builds the devcontainer image (if needed) and runs OpenCode using docker compose.

    Environment variables are loaded with precedence (lowest to highest):
    1. Global env file (~/.config/opencode/.env, auto-loaded if present)
    2. Base .opencode/.env file
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
        ocframework launch --rebuild
        ocframework launch --env-file prod.env
        ocframework launch -e API_KEY=$HOME/.key -e DEBUG=true
        ocframework launch --server
        ocframework launch --server=5000
    """
    cwd = Path.cwd()

    valid, error = validate_runtime_context(cwd)
    if not valid:
        typer.secho(f"Error: {error}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)

    repo_root = get_repo_root(cwd)
    if repo_root is None:
        typer.secho(
            "Error: Could not determine repository root", fg=typer.colors.RED, err=True
        )
        raise typer.Exit(1)

    env_path = repo_root / ".opencode" / ".env"
    global_env_path = get_config_root() / "opencode" / ".env"
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
        raise typer.Exit(1)
    except FileNotFoundError as e:
        typer.secho(f"Error: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)
    except Exception as e:
        typer.secho(f"Error loading environment: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)

    # Print any warnings (e.g., global env file failed to parse)
    for warning in warnings:
        typer.secho(f"Warning: {warning}", fg=typer.colors.YELLOW)

    subprocess_env = build_docker_env(final_env, docker_context)

    opencode_dir = repo_root / ".opencode"
    compose_path = opencode_dir / "docker-compose.yaml"

    if not compose_path.exists():
        typer.secho(
            "Error: docker-compose.yaml not found. Run 'ocframework init' first.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(1)

    image_id = None

    if force and remove_image_id(opencode_dir):
        typer.echo("Removed cached image ID; image will be rebuilt.")

    if rebuild:
        if update_features(opencode_dir, repo_root.name):
            typer.echo("Feature configuration changed; rebuilding image...")
        else:
            typer.echo("Building devcontainer image (--rebuild specified)...")
        image_id = _build_image(opencode_dir, repo_root, subprocess_env)
    else:
        image_id = load_image_id(opencode_dir)
        if image_id:
            typer.echo(f"Using existing image: {image_id}")
        else:
            typer.echo("Building devcontainer image (no cached image ID found)...")
            image_id = _build_image(opencode_dir, repo_root, subprocess_env)

    save_image_id(opencode_dir, image_id)

    subprocess_env["OCF_IMAGE_ID"] = image_id
    subprocess_env["PWD"] = str(repo_root)

    detected_ports = ComposeGenerator.detect_ports(compose_path.read_text())
    reserved_host_ports = _extract_host_ports(detected_ports)

    server, remaining_args = _extract_server_arg(ctx.args)
    ctx.args[:] = remaining_args

    server_host_port: Optional[int] = None
    if server is not None:
        server_host_port = _resolve_server_port(
            server, ctx.args, reserved_host_ports=reserved_host_ports
        )

    container_name = _extract_container_name(compose_path)

    # Handle existing container: attach if running, otherwise remove
    if container_name:
        status = _get_container_status(container_name, subprocess_env)
        if status == "running" and not force:
            typer.echo(f"Container '{container_name}' is already running. Attaching...")
            attach_result = subprocess.run(
                ["docker", "attach", container_name],
                env=subprocess_env,
                cwd=repo_root,
            )
            attach_rc = attach_result.returncode
            if attach_rc < 128 and attach_rc != 0:
                # Attach failure (not a signal). 128+N = killed by signal N (e.g. 130 = SIGINT/Ctrl+C),
                # which is an intentional interrupt, not a failure.
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
                f"{prefix} container '{container_name}' (status: {status}). Removing...",
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

    typer.echo("Launching OpenCode...")

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
        run_cmd.extend(["--publish", f"{server_host_port}:{SERVER_CONTAINER_PORT}"])
    elif detected_ports:
        run_cmd.append("--service-ports")

    if container_name:
        run_cmd.extend(["--name", container_name])

    for key, value in final_env.items():
        run_cmd.extend(["--env", f"{key}={value}"])

    if server_host_port is not None:
        run_cmd.extend(
            [
                "opencode",
                "serve",
                "--hostname",
                "0.0.0.0",
                "--port",
                str(SERVER_CONTAINER_PORT),
            ]
        )
    else:
        run_cmd.append("opencode")
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
        raise typer.Exit(130)  # 130 is standard exit code for SIGINT
    except Exception:
        # Re-raise any other exception
        raise


if __name__ == "__main__":
    app()
