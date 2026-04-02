"""Exception hierarchy for the OpenCode Framework."""

from .base import (
    FrameworkError,
    ConfigurationError,
    GitError,
    ValidationError,
    WorktreeError,
    RuntimeError,
    GenerationError,
    EnvError,
    PreflighjError,
    WizardError,
)
from .validation import (
    ProjectSetupError,
    FrameworkInstallationError,
    EnvironmentError,
    GitRepositoryError,
    DirectoryStructureError,
)
from .generator import (
    TemplateError,
    TemplateNotFoundError,
    TemplateRenderError,
    DevcontainerGenerationError,
    ConfigGenerationError,
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
