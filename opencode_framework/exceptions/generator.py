"""Generator-specific exceptions."""

from .base import GenerationError


class TemplateError(GenerationError):
    """Template loading or rendering error."""
    pass


class TemplateNotFoundError(TemplateError):
    """Template file not found."""
    pass


class TemplateRenderError(TemplateError):
    """Template rendering failed."""
    pass


class DevcontainerGenerationError(GenerationError):
    """Devcontainer file generation failed."""
    pass


class ConfigGenerationError(GenerationError):
    """Configuration file generation failed."""
    pass
