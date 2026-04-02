"""Generator-specific exceptions."""

from .base import GenerationError


class TemplateError(GenerationError):
    """Template loading or rendering error."""


class TemplateNotFoundError(TemplateError):
    """Template file not found."""


class TemplateRenderError(TemplateError):
    """Template rendering failed."""


class DevcontainerGenerationError(GenerationError):
    """Devcontainer file generation failed."""


class ConfigGenerationError(GenerationError):
    """Configuration file generation failed."""
