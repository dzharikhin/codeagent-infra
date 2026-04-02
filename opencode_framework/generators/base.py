"""Base generator class and context definitions."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from opencode_framework.config import GlobalSettings


@dataclass
class GenerationContext:
    """Context for generating .opencode/ contents."""
    
    repo_root: Path
    opencode_dir: Path
    branch_name: str
    devcontainer_strategy: str
    optional_features: List[str]
    editor_choice: str
    global_settings: GlobalSettings
    existing_devcontainer: Optional[dict] = None


class FileGenerator(ABC):
    """Abstract base class for file generators."""
    
    @abstractmethod
    def generate(self, ctx: GenerationContext) -> None:
        """Generate file(s) in the given context.
        
        Args:
            ctx: Generation context with all necessary information
        """
