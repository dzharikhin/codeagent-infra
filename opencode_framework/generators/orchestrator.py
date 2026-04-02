"""Orchestrator for coordinating file generation."""

import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional

from opencode_framework.config import discover_global_settings
from opencode_framework.wizard import WizardResult

from .base import GenerationContext
from .devcontainer import DevcontainerGenerator
from .config_files import ConfigFilesGenerator
from .documentation import DocumentationGenerator
from .compose import ComposeGenerator


class GenerationOrchestrator:
    """Coordinates the generation of all .opencode/ directory contents."""
    
    def __init__(self):
        """Initialize the orchestrator with all generators."""
        self.devcontainer_gen = DevcontainerGenerator()
        self.config_gen = ConfigFilesGenerator()
        self.docs_gen = DocumentationGenerator()
        self.compose_gen = ComposeGenerator()
    
    def generate(self, repo_root: Path, wizard_result: WizardResult) -> None:
        """Generate the complete .opencode/ directory structure.
        
        Args:
            repo_root: Root of the repository
            wizard_result: Results from the initialization wizard
        """
        opencode_dir = repo_root / ".opencode"
        
        if not opencode_dir.exists():
            opencode_dir.mkdir(parents=True, exist_ok=True)
        
        existing_dc = None
        if wizard_result.existing_devcontainer:
            existing_dc = wizard_result.existing_devcontainer.content
        
        ctx = GenerationContext(
            repo_root=repo_root,
            opencode_dir=opencode_dir,
            branch_name=wizard_result.branch_name,
            devcontainer_strategy=wizard_result.devcontainer_strategy,
            optional_features=wizard_result.optional_features,
            editor_choice=wizard_result.editor_choice,
            global_settings=discover_global_settings(),
            existing_devcontainer=existing_dc,
        )
        
        # Generate all files in order
        self.devcontainer_gen.generate(ctx)
        self.config_gen.generate(ctx)
        self.compose_gen.generate(ctx)
        self.docs_gen.generate(ctx)
        
        # Create runtime_data directories
        runtime_data = opencode_dir / "runtime_data"
        runtime_data.mkdir(exist_ok=True)
        (runtime_data / ".cache").mkdir(exist_ok=True)
        (runtime_data / ".local" / "share").mkdir(parents=True, exist_ok=True)
        (runtime_data / ".local" / "state").mkdir(parents=True, exist_ok=True)
    
    @staticmethod
    def backup_existing_opencode(repo_root: Path) -> Optional[Path]:
        """Backup existing .opencode/ directory.
        
        Creates .opencode.backup-<timestamp> in project root.
        
        Args:
            repo_root: Root of the repository
            
        Returns:
            Path to backup directory, or None if nothing to backup
        """
        opencode_dir = repo_root / ".opencode"
        if not opencode_dir.exists():
            return None
        
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        backup_path = repo_root / f".opencode.backup-{timestamp}"
        
        shutil.move(str(opencode_dir), str(backup_path))
        return backup_path
