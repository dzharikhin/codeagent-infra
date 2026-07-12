"""Exception hierarchy for the OpenCode Framework."""

from .base import (
    ConfigurationError,
    EnvError,
    FrameworkError,
    GenerationError,
    GitError,
    PreflighjError,
    RuntimeError,
    ValidationError,
    WizardError,
    WorktreeError,
)
from .generator import (
    ConfigGenerationError,
    DevcontainerGenerationError,
    TemplateError,
    TemplateNotFoundError,
    TemplateRenderError,
)
from .validation import (
    DirectoryStructureError,
    EnvironmentError,
    FrameworkInstallationError,
    GitRepositoryError,
    ProjectSetupError,
)

__all__ = [
    # Base exceptions
    "FrameworkError",
    "ConfigurationError",
    "GitError",
    "ValidationError",
    "WorktreeError",
    "RuntimeError",
    "GenerationError",
    "EnvError",
    "PreflighjError",
    "WizardError",
    # Validation exceptions
    "ProjectSetupError",
    "FrameworkInstallationError",
    "EnvironmentError",
    "GitRepositoryError",
    "DirectoryStructureError",
    # Generator exceptions
    "TemplateError",
    "TemplateNotFoundError",
    "TemplateRenderError",
    "DevcontainerGenerationError",
    "ConfigGenerationError",
]
