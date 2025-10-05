"""
Stats command for Dockyard CLI
"""
import sys
import os
import click

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import dockyard_pb2

from cli.commands.base import BaseCommand
from cli.formatters.table import format_table
from cli.formatters.utils import format_bytes


class StatsCommand(BaseCommand):
    """Stats command implementation"""

    def get_stats(self, container_identifiers=None, no_stream=False):
        """Get container resource statistics

        Args:
            container_identifiers: List of container names/IDs (None = all)
            no_stream: Disable streaming (single snapshot)
        """
        try:
            if not no_stream:
                click.echo("Streaming container statistics... (Press Ctrl+C to stop)")

            request = dockyard_pb2.StatsRequest(
                container_identifiers=container_identifiers or [],
                stream=not no_stream
            )

            first_iteration = True

            # Stream stats
            for response in self.client.stub.GetStats(request):
                if not response.success:
                    click.echo(f"Error: {response.message}", err=True)
                    sys.exit(1)

                if not response.stats:
                    if first_iteration:
                        click.echo("No running containers found")
                    return

                # Format stats as table
                self._display_stats(response.stats, clear_screen=not first_iteration and not no_stream)
                first_iteration = False

        except KeyboardInterrupt:
            click.echo("\nStats streaming stopped", err=True)
        except Exception as e:
            self.handle_error(e)

    def _display_stats(self, stats, clear_screen=False):
        """Display statistics as formatted table

        Args:
            stats: List of ContainerStats
            clear_screen: Clear screen before displaying
        """
        if clear_screen:
            # Move cursor to top and clear screen
            click.echo('\033[H\033[J', nl=False)

        headers = ["CONTAINER", "NAME", "CPU %", "MEM USAGE / LIMIT", "MEM %", "NET I/O", "BLOCK I/O", "PIDS"]
        rows = []

        for stat in stats:
            mem_usage = format_bytes(stat.memory_usage)
            mem_limit = format_bytes(stat.memory_limit)
            net_io = f"{format_bytes(stat.network_rx)} / {format_bytes(stat.network_tx)}"
            block_io = f"{format_bytes(stat.block_read)} / {format_bytes(stat.block_write)}"

            rows.append([
                stat.container_id,
                stat.name,
                f"{stat.cpu_percentage:.2f}%",
                f"{mem_usage} / {mem_limit}",
                f"{stat.memory_percentage:.2f}%",
                net_io,
                block_io,
                str(stat.pids)
            ])

        table = format_table(headers, rows)
        click.echo(table)
