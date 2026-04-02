"""CLI entrypoint for ocframework."""

import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional, List

import typer

from opencode_framework import __version__
from opencode_framework.config import (
    discover_global_settings,
    validate_framework_repo,
    get_framework_validation_error,
    get_config_root,
    get_local_data_home,
)
from opencode_framework.preflight import (
    run_preflight_checks,
    opencode_directory_exists,
    get_repo_root,
)
from opencode_framework.wizard import run_wizard
from opencode_framework.generators import GenerationOrchestrator
from opencode_framework.generators.documentation import DocumentationGenerator
from opencode_framework.git_ops import (
    setup_opencode_worktree,
    remove_worktree,
    is_worktree,
)
from opencode_framework.runtime import (
    validate_runtime_context,
    load_env_with_overrides,
    build_devcontainer_env,
    identify_resolved_variables,
    add_remote_env_to_command,
    parse_cli_env_vars,
    EnvError,
)
from dotenv import dotenv_values


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
            typer.secho(f"framework repo path: {framework_path} (INVALID)", fg=typer.colors.RED)
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
        typer.secho("Error: Framework repository is invalid.", fg=typer.colors.RED, err=True)
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
            
            shutil.copytree(opencode_dir, backup_path)
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
    typer.echo("\nopencode is started on attach via postAttachCommand.")


@app.command()
def launch(
    docker_context: str = typer.Option(
        "rootless",
        "--docker-context",
        help="Docker context to use for devcontainer",
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
) -> None:
    """Launch the devcontainer for this project.
    
    Validates that the current directory is a Git repository root with
    a properly initialized .opencode/ directory, then runs devcontainer up.
    
    Environment variables are loaded with precedence (lowest to highest):
    1. Base .opencode/.env file
    2. Override file (--env-file)
    3. Command-line variables (-e KEY=VALUE)
    
    Supports:
    - Variable interpolation: $VAR, ${VAR}, ${VAR:-default}
    - Export statements: export KEY=VALUE
    - Comments: # comment
    - Quoted values: KEY="value with spaces"
    
    DOCKER_CONTEXT is set to 'rootless' by default. Use --docker-context to override.
    
    Examples:
        ocframework launch
        ocframework launch --env-file prod.env
        ocframework launch -e API_KEY=$HOME/.key -e DEBUG=true
        ocframework launch --env-file prod.env -e PORT=9000
    """
    cwd = Path.cwd()
    
    # Validate runtime context
    valid, error = validate_runtime_context(cwd)
    if not valid:
        typer.secho(f"Error: {error}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)
    
    # Get repo root
    repo_root = get_repo_root(cwd)
    if repo_root is None:
        typer.secho("Error: Could not determine repository root", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)
    
    # Load raw base environment (before resolution, for comparison)
    env_path = repo_root / ".opencode" / ".env"
    base_env = {}
    if env_path.exists():
        base_env = dict(dotenv_values(env_path, interpolate=False))
        base_env = {k: v if v is not None else "" for k, v in base_env.items()}
    
    # Load resolved environment with overrides
    try:
        final_env = load_env_with_overrides(
            base_env_path=env_path,
            override_env_path=env_file,
            cli_env_vars=env_vars,
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
    
    # Parse CLI variables for tracking
    cli_env_dict = {}
    if env_vars:
        try:
            cli_env_dict = parse_cli_env_vars(env_vars)
        except ValueError as e:
            typer.secho(f"Error: {e}", fg=typer.colors.RED, err=True)
            raise typer.Exit(1)
    
    # Identify resolved variables to pass via --remote-env
    resolved_vars = identify_resolved_variables(base_env, final_env, cli_env_dict)
    
    # Build subprocess environment
    subprocess_env = build_devcontainer_env(final_env, docker_context)
    
    # Prepare command
    cmd = [
        "devcontainer",
        "up",
        "--config",
        ".opencode/devcontainer.json",
        "--workspace-folder",
        ".",
    ]
    
    # Add resolved variables as --remote-env flags
    cmd = add_remote_env_to_command(cmd, resolved_vars)
    
    # Show what we're doing
    typer.echo(f"Launching devcontainer with DOCKER_CONTEXT={docker_context}...")
    if env_file:
        typer.echo(f"Using override file: {env_file}")
    if env_vars:
        typer.echo(f"Applied {len(env_vars)} command-line variable(s)")
    if resolved_vars:
        typer.echo(f"Passing {len(resolved_vars)} resolved variable(s) via --remote-env")
    
    # Execute
    result = subprocess.run(cmd, env=subprocess_env, cwd=repo_root)
    raise typer.Exit(result.returncode)


@app.command(context_settings={"allow_extra_args": True, "ignore_unknown_options": True})
def exec(
    ctx: typer.Context,
    docker_context: str = typer.Option(
        "rootless",
        "--docker-context",
        help="Docker context to use for devcontainer",
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
) -> None:
    """Execute a command inside the devcontainer.
    
    Validates that the current directory is a Git repository root with
    a properly initialized .opencode/ directory, then runs devcontainer exec.
    
    Environment variables are loaded with precedence (lowest to highest):
    1. Base .opencode/.env file
    2. Override file (--env-file)
    3. Command-line variables (-e KEY=VALUE)
    
    Supports:
    - Variable interpolation: $VAR, ${VAR}, ${VAR:-default}
    - Export statements: export KEY=VALUE
    - Comments: # comment
    - Quoted values: KEY="value with spaces"
    
    The command to execute must follow '--'. For example:
        ocframework exec -- opencode debug config
        ocframework exec -- bash
        ocframework exec --env-file prod.env -e KEY=value -- opencode debug config
    """
    args = ctx.args
    if not args:
        typer.secho(
            "Error: No command specified. Use '--' before the command.",
            fg=typer.colors.RED,
            err=True,
        )
        typer.echo("Example: ocframework exec -- opencode debug config")
        raise typer.Exit(1)
    
    cwd = Path.cwd()
    
    # Validate runtime context
    valid, error = validate_runtime_context(cwd)
    if not valid:
        typer.secho(f"Error: {error}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)
    
    # Get repo root
    repo_root = get_repo_root(cwd)
    if repo_root is None:
        typer.secho("Error: Could not determine repository root", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)
    
    # Load raw base environment (before resolution, for comparison)
    env_path = repo_root / ".opencode" / ".env"
    base_env = {}
    if env_path.exists():
        base_env = dict(dotenv_values(env_path, interpolate=False))
        base_env = {k: v if v is not None else "" for k, v in base_env.items()}
    
    # Load resolved environment with overrides
    try:
        final_env = load_env_with_overrides(
            base_env_path=env_path,
            override_env_path=env_file,
            cli_env_vars=env_vars,
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
    
    # Parse CLI variables for tracking
    cli_env_dict = {}
    if env_vars:
        try:
            cli_env_dict = parse_cli_env_vars(env_vars)
        except ValueError as e:
            typer.secho(f"Error: {e}", fg=typer.colors.RED, err=True)
            raise typer.Exit(1)
    
    # Identify resolved variables to pass via --remote-env
    resolved_vars = identify_resolved_variables(base_env, final_env, cli_env_dict)
    
    # Build subprocess environment
    subprocess_env = build_devcontainer_env(final_env, docker_context)
    
    # Prepare command
    cmd = [
        "devcontainer",
        "exec",
        "--config",
        ".opencode/devcontainer.json",
        "--workspace-folder",
        ".",
    ]
    
    # Add resolved variables as --remote-env flags
    cmd = add_remote_env_to_command(cmd, resolved_vars)
    
    # Append the command to execute
    cmd.extend(list(args))
    
    # Execute
    result = subprocess.run(cmd, env=subprocess_env, cwd=repo_root)
    raise typer.Exit(result.returncode)


if __name__ == "__main__":
    app()
