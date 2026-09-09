"""Exception hierarchy for the OpenCode Framework."""

from typing import Optional


class FrameworkError(Exception):
    """Base exception for the OpenCode Framework.

    Provides context information for better error reporting.
    """

    def __init__(
        self,
        message: str,
        remediation: Optional[str] = None,
        context: Optional[dict] = None,
    ):
        """Initialize framework error.

        Args:
            message: Error message
            remediation: Optional fix/remediation suggestion
            context: Optional context dictionary for debugging
        """
        self.message = message
        self.remediation = remediation
        self.context = context or {}
        super().__init__(self._format_message())

    def _format_message(self) -> str:
        """Format error message with context."""
        msg = self.message

        if self.context:
            context_lines = [f"  {key}: {value}" for key, value in self.context.items()]
            msg += "\nContext:\n" + "\n".join(context_lines)

        if self.remediation:
            msg += f"\nRemediation: {self.remediation}"

        return msg


class ValidationError(FrameworkError):
    """Validation errors."""


class PortAllocationError(FrameworkError):
    """Failed to allocate a free host port."""


__all__ = [
    "FrameworkError",
    "ValidationError",
    "PortAllocationError",
]
