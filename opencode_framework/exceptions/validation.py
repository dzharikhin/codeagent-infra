"""Validation-specific exceptions."""

from .base import ValidationError


class ProjectSetupError(ValidationError):
    """Project setup validation failed."""


class FrameworkInstallationError(ValidationError):
    """Framework installation validation failed."""


class EnvironmentError(ValidationError):
    """Environment validation failed."""


class GitRepositoryError(ValidationError):
    """Git repository validation failed."""


class DirectoryStructureError(ValidationError):
    """Directory structure validation failed."""
