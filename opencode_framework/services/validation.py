"""Validation service for project setup."""

from pathlib import Path
from typing import Optional, List

from opencode_framework.core import GitOperations, ConfigManager
from opencode_framework.models import ValidationResult
from opencode_framework.exceptions import ValidationError


class ValidationService:
    """Service that handles all validation logic."""
    
    def __init__(self):
        """Initialize validation service."""
        self.git = GitOperations
        self.config = ConfigManager
    
    def validate_project_setup(self, path: Path) -> ValidationResult:
        """Validate that project directory is ready for initialization.
        
        Checks:
        - Current directory is inside a Git tree
        - Current directory is at repository root
        - Repository is not bare
        - Git index has no staged changes
        
        Args:
            path: Path to validate
            
        Returns:
            ValidationResult with validation status and errors
        """
        errors = []
        warnings = []
        
        # Check if inside git tree
        if not self.git.is_inside_git_tree(path):
            errors.append(
                "Current directory is not inside a Git working tree. "
                "Please initialize a git repository first with: git init"
            )
            return ValidationResult(valid=False, errors=errors, warnings=warnings)
        
        # Get repo root
        repo_root = self.git.get_repo_root(path)
        if repo_root is None:
            errors.append("Cannot determine repository root")
            return ValidationResult(valid=False, errors=errors, warnings=warnings)
        
        # Check if at repo root
        if path.resolve() != repo_root.resolve():
            errors.append(
                f"Current directory is not at repository root. "
                f"Please run from: {repo_root}"
            )
            return ValidationResult(valid=False, errors=errors, warnings=warnings)
        
        # Check if bare repository
        if self.git.is_bare_repository(path):
            errors.append("Repository is bare. Cannot initialize in a bare repository")
            return ValidationResult(valid=False, errors=errors, warnings=warnings)
        
        # Check for staged changes
        if self.git.has_staged_changes(path):
            errors.append(
                "Git index has staged changes. "
                "Please commit or unstage all changes before initializing"
            )
            return ValidationResult(valid=False, errors=errors, warnings=warnings)
        
        return ValidationResult(valid=True, errors=[], warnings=warnings)
    
    def validate_framework_installation(self) -> ValidationResult:
        """Validate that framework is properly installed.
        
        Returns:
            ValidationResult with validation status
        """
        errors = []
        warnings = []
        
        # Discover global settings
        settings = self.config.discover_global_settings()
        
        # Check framework repository
        if not settings.framework_repo_path:
            errors.append(
                "Framework repository not found. "
                "The framework must be installed as an editable package from a git clone: "
                "pipx install -e <path-to-framework-git-clone>"
            )
            return ValidationResult(valid=False, errors=errors, warnings=warnings)
        
        # Validate framework repo
        valid, missing = self.config.validate_framework_repo(
            Path(settings.framework_repo_path)
        )
        if not valid:
            errors.append(
                self.config.get_framework_validation_error(
                    missing,
                    settings.framework_repo_path,
                )
            )
            return ValidationResult(valid=False, errors=errors, warnings=warnings)
        
        return ValidationResult(valid=True, errors=[], warnings=warnings)
    
    def validate_environment(self, env_vars: dict) -> ValidationResult:
        """Validate environment variables.
        
        Args:
            env_vars: Environment variables to validate
            
        Returns:
            ValidationResult with validation status
        """
        errors = []
        warnings = []
        
        # Check for required environment variables if any
        # This can be extended as needed
        
        return ValidationResult(valid=True, errors=errors, warnings=warnings)
