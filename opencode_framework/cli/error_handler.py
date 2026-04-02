"""CLI error handling and formatting."""

import sys
from typing import Optional

import typer

from opencode_framework.exceptions import FrameworkError


class CLIErrorHandler:
    """Centralized CLI error handling and formatting."""
    
    @staticmethod
    def handle_error(
        error: Exception,
        exit_code: int = 1,
        debug: bool = False,
    ) -> None:
        """Handle and display an error to the user.
        
        Args:
            error: The exception that occurred
            exit_code: Exit code to use when calling typer.Exit
            debug: Whether to show debug information
        """
        if isinstance(error, FrameworkError):
            CLIErrorHandler._handle_framework_error(error, debug)
        else:
            CLIErrorHandler._handle_generic_error(error, debug)
        
        raise typer.Exit(exit_code)
    
    @staticmethod
    def _handle_framework_error(error: FrameworkError, debug: bool = False) -> None:
        """Handle a framework error with proper formatting.
        
        Args:
            error: The framework error
            debug: Whether to show debug information
        """
        # Display main error message
        typer.secho(
            f"Error: {error.message}",
            fg=typer.colors.RED,
            err=True,
        )
        
        # Display remediation if available
        if error.remediation:
            typer.secho(
                f"\nRemediation: {error.remediation}",
                fg=typer.colors.YELLOW,
                err=True,
            )
        
        # Display context if in debug mode
        if debug and error.context:
            typer.secho(
                "\nDebug Context:",
                fg=typer.colors.BRIGHT_BLUE,
                err=True,
            )
            for key, value in error.context.items():
                typer.echo(f"  {key}: {value}", err=True)
    
    @staticmethod
    def _handle_generic_error(error: Exception, debug: bool = False) -> None:
        """Handle a generic exception.
        
        Args:
            error: The exception
            debug: Whether to show debug information
        """
        typer.secho(
            f"Error: {str(error)}",
            fg=typer.colors.RED,
            err=True,
        )
        
        if debug:
            import traceback
            typer.secho(
                "\nTraceback:",
                fg=typer.colors.BRIGHT_BLUE,
                err=True,
            )
            traceback.print_exc()
    
    @staticmethod
    def handle_validation_error(
        error: FrameworkError,
        errors: Optional[list] = None,
        warnings: Optional[list] = None,
    ) -> None:
        """Handle validation-related errors with detailed reporting.
        
        Args:
            error: The validation error
            errors: List of validation error messages
            warnings: List of validation warning messages
        """
        typer.secho(
            f"Validation Failed: {error.message}",
            fg=typer.colors.RED,
            err=True,
        )
        
        if errors:
            typer.secho("\nErrors:", fg=typer.colors.RED, err=True)
            for error_msg in errors:
                typer.echo(f"  • {error_msg}", err=True)
        
        if warnings:
            typer.secho("\nWarnings:", fg=typer.colors.YELLOW, err=True)
            for warning_msg in warnings:
                typer.echo(f"  • {warning_msg}", err=True)
        
        if error.remediation:
            typer.secho(
                f"\nRemediation: {error.remediation}",
                fg=typer.colors.YELLOW,
                err=True,
            )
        
        raise typer.Exit(1)
    
    @staticmethod
    def success(message: str) -> None:
        """Display a success message.
        
        Args:
            message: Success message to display
        """
        typer.secho(message, fg=typer.colors.GREEN)
    
    @staticmethod
    def warning(message: str) -> None:
        """Display a warning message.
        
        Args:
            message: Warning message to display
        """
        typer.secho(message, fg=typer.colors.YELLOW)
    
    @staticmethod
    def info(message: str) -> None:
        """Display an info message.
        
        Args:
            message: Info message to display
        """
        typer.echo(message)
