"""
Base command class for Dockyard CLI
"""
import sys
import click


class BaseCommand:
    """Base class for all CLI commands"""

    def __init__(self, client):
        """Initialize command

        Args:
            client: DockyardClient instance
        """
        self.client = client

    def handle_error(self, error, exit_code: int = 1):
        """Handle command errors

        Args:
            error: Error object or message
            exit_code: Exit code
        """
        error_msg = str(error)
        click.echo(f"Error: {error_msg}", err=True)
        sys.exit(exit_code)
