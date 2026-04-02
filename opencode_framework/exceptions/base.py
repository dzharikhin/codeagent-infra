"""Base exception hierarchy."""


class FrameworkError(Exception):
    """Base exception for the OpenCode Framework.
    
    Provides context information for better error reporting.
    """
    
    def __init__(
        self,
        message: str,
        remediation: str = None,
        context: dict = None,
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
            context_lines = [
                f"  {key}: {value}"
                for key, value in self.context.items()
            ]
            msg += "\nContext:\n" + "\n".join(context_lines)
        
        if self.remediation:
            msg += f"\nRemediation: {self.remediation}"
        
        return msg


class ConfigurationError(FrameworkError):
    """Configuration-related errors."""
    pass


class GitError(FrameworkError):
    """Git operation errors."""
    pass


class ValidationError(FrameworkError):
    """Validation errors."""
    pass


class WorktreeError(GitError):
    """Git worktree-specific errors."""
    pass


class RuntimeError(FrameworkError):
    """Runtime environment errors."""
    pass


class GenerationError(FrameworkError):
    """File generation errors."""
    pass


class EnvError(RuntimeError):
    """Environment variable and .env file errors."""
    pass


class PreflighjError(FrameworkError):
    """Preflight check errors."""
    pass


class WizardError(FrameworkError):
    """Wizard interaction errors."""
    pass
