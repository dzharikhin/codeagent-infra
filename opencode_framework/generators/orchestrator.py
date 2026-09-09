"""Orchestrator for coordinating file generation."""

import shutil
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from opencode_framework.agent.registry import get_tool_spec
from opencode_framework.config import discover_global_settings
from opencode_framework.sandbox.compose import ComposeGenerator
from opencode_framework.sandbox.devcontainer import DevcontainerGenerator

from .base import GenerationContext
from .config_files import ConfigFilesGenerator
from .documentation import DocumentationGenerator

if TYPE_CHECKING:
    from opencode_framework.wizard import WizardResult


class GenerationOrchestrator:
    """Coordinates the generation of the active tool's config worktree."""

    def __init__(self):
        """Initialize the orchestrator with all generators."""
        self.devcontainer_gen = DevcontainerGenerator()
        self.config_gen = ConfigFilesGenerator()
        self.docs_gen = DocumentationGenerator()
        self.compose_gen = ComposeGenerator()

    def generate(self, repo_root: Path, wizard_result: "WizardResult") -> None:
        """Generate the complete config worktree for the selected tool.

        Args:
            repo_root: Root of the repository
            wizard_result: Results from the initialization wizard
        """
        config_dir = repo_root / get_tool_spec(wizard_result.agent_tool).config_dirname

        if not config_dir.exists():
            config_dir.mkdir(parents=True, exist_ok=True)

        ctx = GenerationContext(
            repo_root=repo_root,
            config_dir=config_dir,
            branch_name=wizard_result.branch_name,
            optional_features=wizard_result.optional_features,
            global_settings=discover_global_settings(),
            port_mappings=wizard_result.port_mappings,
            java_build_tools=wizard_result.java_build_tools,
            agent_tool=wizard_result.agent_tool,
        )

        # Generate all files in order
        self.devcontainer_gen.generate(ctx)
        self.config_gen.generate(ctx)
        self.compose_gen.generate(ctx)
        self.docs_gen.generate(ctx)

        # Create runtime_data directories
        runtime_data = config_dir / "runtime_data"
        runtime_data.mkdir(exist_ok=True)
        (runtime_data / ".cache").mkdir(exist_ok=True)
        (runtime_data / ".local" / "share").mkdir(parents=True, exist_ok=True)
        (runtime_data / ".local" / "state").mkdir(parents=True, exist_ok=True)

        # Create symlink to framework-nuts-and-bolts
        framework_repo_path = ctx.global_settings.framework_repo_path
        if framework_repo_path:
            nuts_and_bolts_src = Path(framework_repo_path) / "framework-nuts-and-bolts"
            nuts_and_bolts_link = config_dir / "framework-nuts-and-bolts"
            if nuts_and_bolts_src.is_dir() and not nuts_and_bolts_link.exists():
                nuts_and_bolts_link.symlink_to(nuts_and_bolts_src)

    @staticmethod
    def backup_existing_config_dir(repo_root: Path, agent_tool: str) -> Optional[Path]:
        """Backup an existing config worktree directory.

        Creates <dirname>.backup-<timestamp> in project root.

        Args:
            repo_root: Root of the repository
            agent_tool: Agent tool name ("opencode" | "qwen")

        Returns:
            Path to backup directory, or None if nothing to backup
        """
        config_dir = repo_root / get_tool_spec(agent_tool).config_dirname
        if not config_dir.exists():
            return None

        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        backup_path = repo_root / f"{config_dir.name}.backup-{timestamp}"

        shutil.move(str(config_dir), str(backup_path))
        return backup_path
