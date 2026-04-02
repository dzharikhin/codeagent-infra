"""Result data models."""

from dataclasses import dataclass
from pathlib import Path
from typing import List


@dataclass
class GitResult:
    """Result of a git operation."""
    
    success: bool
    stdout: str
    stderr: str
    returncode: int
    
    def __bool__(self) -> bool:
        """Allow boolean check: if git_result:"""
        return self.success


@dataclass
class ValidationResult:
    """Result of validation operation."""
    
    valid: bool
    errors: List[str]
    warnings: List[str] = None
    
    def __post_init__(self):
        """Ensure warnings is a list."""
        if self.warnings is None:
            self.warnings = []


@dataclass
class GeneratedFile:
    """A generated file with its content."""
    
    path: Path
    content: str
    description: str = ""
