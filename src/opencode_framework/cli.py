"""CLI entrypoint for ocframework."""

import sys
from pathlib import Path
from typing import Optional

import typer

from opencode_framework import __version__
from opencode_framework.config import discover_global_settings, GlobalSettings


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
    typer.echo(f"framework repo path: {_get_framework_repo_path()}")
    typer.echo(f"global config found: {settings.global_config_found}")
    if settings.global_config_found:
        typer.echo(f"global config path: {settings.global_config_path}")
    typer.echo(f"global auth.json found: {settings.global_auth_found}")
    if settings.global_auth_found:
        typer.echo(f"global auth.json path: {settings.global_auth_path}")


def _get_framework_repo_path() -> Optional[str]:
    """Get the framework repository path from the installed package location."""
    package_path = Path(__file__).resolve().parent
    repo_root = package_path.parent.parent
    if (repo_root / ".git").is_dir():
        return str(repo_root)
    return str(package_path)


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
    from opencode_framework.preflight import run_preflight_checks, opencode_directory_exists
    from opencode_framework.wizard import run_wizard
    from opencode_framework.generator import generate_opencode_directory, backup_existing_opencode
    from opencode_framework.git_ops import setup_opencode_worktree, remove_worktree, is_worktree
    
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
            if not remove_worktree(opencode_dir, cwd=repo_path):
                typer.secho(
                    "Failed to remove existing worktree",
                    fg=typer.colors.RED,
                    err=True,
                )
                raise typer.Exit(1)
        backup_path = backup_existing_opencode(repo_path)
        if backup_path:
            typer.echo(f"Backup created at: {backup_path}")
    
    typer.echo("Running setup wizard...")
    wizard_result = run_wizard(repo_path, result)
    
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
    generate_opencode_directory(repo_path, wizard_result)
    
    from opencode_framework.generator import _get_launch_commands
    commands = _get_launch_commands()
    
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
) -> None:
    """Launch the devcontainer for this project.
    
    Validates that the current directory is a Git repository root with
    a properly initialized .opencode/ directory, then runs devcontainer up.
    
    DOCKER_CONTEXT is set to 'rootless' by default for the devcontainer
    subprocess. Use --docker-context to override.
    """
    import subprocess
    
    from opencode_framework.runtime import (
        validate_runtime_context,
        load_and_expand_env,
        build_devcontainer_env,
    )
    
    cwd = Path.cwd()
    
    valid, error = validate_runtime_context(cwd)
    if not valid:
        typer.secho(f"Error: {error}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)
    
    from opencode_framework.preflight import get_repo_root
    repo_root = get_repo_root(cwd)
    if repo_root is None:
        typer.secho("Error: Could not determine repository root", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)
    
    env_path = repo_root / ".opencode" / ".env"
    base_env = load_and_expand_env(env_path)
    subprocess_env = build_devcontainer_env(base_env, docker_context)
    
    cmd = [
        "devcontainer",
        "up",
        "--config",
        ".opencode/devcontainer.json",
        "--workspace-folder",
        ".",
    ]
    
    typer.echo(f"Launching devcontainer with DOCKER_CONTEXT={docker_context}...")
    
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
) -> None:
    """Execute a command inside the devcontainer.
    
    Validates that the current directory is a Git repository root with
    a properly initialized .opencode/ directory, then runs devcontainer exec.
    
    DOCKER_CONTEXT is set to 'rootless' by default for the devcontainer
    subprocess. Use --docker-context to override.
    
    The command to execute must follow '--'. For example:
        ocframework exec -- opencode debug config
        ocframework exec -- bash
    """
    import subprocess
    
    from opencode_framework.runtime import (
        validate_runtime_context,
        load_and_expand_env,
        build_devcontainer_env,
    )
    
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
    
    valid, error = validate_runtime_context(cwd)
    if not valid:
        typer.secho(f"Error: {error}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)
    
    from opencode_framework.preflight import get_repo_root
    repo_root = get_repo_root(cwd)
    if repo_root is None:
        typer.secho("Error: Could not determine repository root", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)
    
    env_path = repo_root / ".opencode" / ".env"
    base_env = load_and_expand_env(env_path)
    subprocess_env = build_devcontainer_env(base_env, docker_context)
    
    cmd = [
        "devcontainer",
        "exec",
        "--config",
        ".opencode/devcontainer.json",
        "--workspace-folder",
        ".",
    ] + list(args)
    
    result = subprocess.run(cmd, env=subprocess_env, cwd=repo_root)
    raise typer.Exit(result.returncode)


if __name__ == "__main__":
    app()
