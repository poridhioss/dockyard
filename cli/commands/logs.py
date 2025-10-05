"""
Logs command for Dockyard CLI
"""
import sys
import os
import click

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import dockyard_pb2

from cli.commands.base import BaseCommand


class LogsCommand(BaseCommand):
    """Logs command implementation"""

    def get_logs(self, container_identifier, follow=False, tail=None, since=None,
                 timestamps=False, no_stdout=False, no_stderr=False):
        """Get container logs

        Args:
            container_identifier: Container name or ID
            follow: Follow log output
            tail: Number of lines from end
            since: Show logs since timestamp/duration
            timestamps: Include timestamps
            no_stdout: Exclude stdout
            no_stderr: Exclude stderr
        """
        try:
            request = dockyard_pb2.LogsRequest(
                container_identifier=container_identifier,
                follow=follow,
                tail=tail or 0,
                since=since or '',
                timestamps=timestamps,
                stdout=not no_stdout,
                stderr=not no_stderr
            )

            # Stream logs
            for response in self.client.stub.GetLogs(request):
                if response.HasField('log'):
                    # Log entry
                    if response.log.data:
                        sys.stdout.buffer.write(response.log.data)
                        sys.stdout.flush()
                elif response.HasField('status'):
                    # Status message
                    if not response.status.success:
                        click.echo(f"Error getting logs: {response.status.message}", err=True)
                        sys.exit(1)

        except KeyboardInterrupt:
            # Graceful exit on Ctrl+C
            click.echo("\nLog streaming stopped", err=True)
        except Exception as e:
            self.handle_error(e)
