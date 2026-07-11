"""Interactive wizard for setup decisions."""

from dataclasses import dataclass
from pathlib import Path
from typing import List
import getpass

import typer

from opencode_framework.features import prompt_feature_changes
from opencode_framework.preflight import PreflightResult


@dataclass
class WizardResult:
    """Collected wizard decisions."""
    
    branch_name: str
    optional_features: List[str]
    editor_choice: str  # "none", "vi", or "nano"
    should_add_to_gitignore: bool
    create_global_config: bool = False


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
    - Global config creation (if missing) - FIRST
    - Branch name with suggested default
    - Devcontainer strategy
    - Optional feature selection
    - Editor preference
    """
    from opencode_framework.config import discover_global_settings, get_config_root
    
    settings = discover_global_settings()
    create_global_config = False
    
    if not settings.global_config_found:
        config_root = get_config_root()
        config_path = config_root / "opencode"
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
    
    optional_features, editor_choice = prompt_feature_changes([], "none")
    
    if check_gitignore_needs_opencode(repo_root):
        typer.secho(
            "\nNote: .opencode/ is not in .gitignore. Consider adding it to avoid committing framework files.",
            fg=typer.colors.YELLOW,
        )
    
    return WizardResult(
        branch_name=branch_name,
        optional_features=optional_features,
        editor_choice=editor_choice,
        should_add_to_gitignore=True,
        create_global_config=create_global_config,
    )
