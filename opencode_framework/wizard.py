"""Interactive wizard for setup decisions."""

import getpass
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

import typer

from opencode_framework.agent.layers import discover_global_layer, expected_global_path
from opencode_framework.agent.registry import (
    DEFAULT_TOOL,
    ToolSpec,
    get_tool_spec,
)
from opencode_framework.exceptions import ValidationError
from opencode_framework.preflight import PreflightResult
from opencode_framework.sandbox.features import (
    prompt_feature_changes,
    prompt_port_mappings,
)


@dataclass
class WizardResult:
    """Collected wizard decisions."""

    branch_name: str
    optional_features: List[str]
    editor_choice: str  # "none", "vi", or "nano"
    should_add_to_gitignore: bool
    create_global_config: bool = False
    port_mappings: List[str] = field(default_factory=list)
    java_build_tools: List[str] = field(default_factory=list)
    agent_tool: str = DEFAULT_TOOL


def suggest_branch_name() -> str:
    """Suggest a branch name based on username."""
    username = getpass.getuser() or "user"
    return f"codeagent-{username}"


def resolve_tool_or_exit(tool: str, hint: Optional[str] = None) -> ToolSpec:
    """Resolve a tool name to its ToolSpec, exiting with remediation on failure.

    Args:
        tool: tool identifier as entered by the user or read from config.
        hint: extra remediation line printed after the error.

    Returns:
        The resolved ToolSpec.

    Raises:
        typer.Exit: when the tool name is not supported.
    """
    try:
        return get_tool_spec(tool)
    except ValidationError as e:
        typer.secho(f"Error: {e.message}", fg=typer.colors.RED, err=True)
        typer.secho(f"Remediation: {e.remediation}", fg=typer.colors.YELLOW, err=True)
        if hint:
            typer.secho(hint, fg=typer.colors.YELLOW, err=True)
        raise typer.Exit(1) from None


def check_gitignore_needs(repo_root: Path, entry: str) -> bool:
    """Check if .gitignore mentions an entry."""
    gitignore_path = repo_root / ".gitignore"
    if not gitignore_path.is_file():
        return True

    content = gitignore_path.read_text()
    return entry not in content


def run_wizard(
    repo_root: Path,
    preflight_result: PreflightResult,
    agent_tool: Optional[str] = None,
) -> WizardResult:
    """Run the interactive setup wizard.

    Asks only for meaningful structural choices:
    - Agent CLI tool (opencode | qwen) - FIRST, unless given via --tool
    - Global config creation (dir-based tools, if missing)
    - Branch name with suggested default
    - Optional feature selection
    - Editor preference
    """
    if agent_tool is None:
        agent_tool = typer.prompt(
            "\nAgent CLI tool (opencode | qwen)",
            default=DEFAULT_TOOL,
            type=str,
        )
    spec = resolve_tool_or_exit(agent_tool)

    create_global_config = False

    if spec.global_config_is_dir:
        layer = discover_global_layer(spec)
        if not layer.global_found:
            config_path = expected_global_path(spec)
            typer.echo(f"\nGlobal config directory not found at: {config_path}")
            create_global_config = typer.confirm(
                "Create global config directory?",
                default=True,
            )

    suggested_branch = suggest_branch_name()

    branch_name = typer.prompt(
        "\nConfig branch name",
        default=suggested_branch,
        type=str,
    )

    optional_features, editor_choice, java_build_tools = prompt_feature_changes(
        [], "none", None
    )

    port_mappings = prompt_port_mappings()

    if check_gitignore_needs(repo_root, ".opencode"):
        typer.secho(
            "\nNote: .opencode/ is not in .gitignore. Consider adding it to avoid committing framework files.",
            fg=typer.colors.YELLOW,
        )

    if spec.name == "qwen" and check_gitignore_needs(repo_root, ".qwen"):
        typer.secho(
            "\nNote: .qwen/ is not in .gitignore. "
            "Add it to avoid committing qwen settings.",
            fg=typer.colors.YELLOW,
        )

    return WizardResult(
        branch_name=branch_name,
        optional_features=optional_features,
        editor_choice=editor_choice,
        should_add_to_gitignore=True,
        create_global_config=create_global_config,
        port_mappings=port_mappings,
        java_build_tools=java_build_tools,
        agent_tool=spec.name,
    )
