"""CLI package for OpenCode Framework."""

from .app import app
from .error_handler import CLIErrorHandler

__all__ = ["app", "CLIErrorHandler"]
