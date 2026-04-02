"""Validation-specific exceptions."""

from .base import ValidationError


class ProjectSetupError(ValidationError):
    """Project setup validation failed."""
    pass


class FrameworkInstallationError(ValidationError):
    """Framework installation validation failed."""
    pass


class EnvironmentError(ValidationError):
    """Environment validation failed."""
    pass


class GitRepositoryError(ValidationError):
    """Git repository validation failed."""
    pass


class DirectoryStructureError(ValidationError):
    """Directory structure validation failed."""
    pass
