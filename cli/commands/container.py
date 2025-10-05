"""
Container management commands for Dockyard CLI
"""
import sys
import os
import click

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import dockyard_pb2

from cli.commands.base import BaseCommand
from cli.formatters.table import print_table
from cli.formatters.utils import format_bytes


class ContainerCommands(BaseCommand):
    """Container management commands"""

    def launch(self, image, name=None, config_file=None):
        """Launch a container

        Args:
            image: Docker image name
            name: Container name
            config_file: Path to config file
        """
        try:
            click.echo("Launching container...")

            request = dockyard_pb2.LaunchRequest(
                image=image,
                name=name or '',
                config_file=config_file or ''
            )

            response = self.client.stub.LaunchContainer(request)

            if response.success:
                click.echo(f"Success: {response.message}")
                click.echo(f"Container ID: {response.container_id}")
            else:
                click.echo(f"Failed: {response.message}", err=True)
                sys.exit(1)

        except Exception as e:
            self.handle_error(e)

    def stop(self, container_identifier, force=False, timeout=10):
        """Stop a container

        Args:
            container_identifier: Container name or ID
            force: Force kill the container
            timeout: Timeout for graceful stop
        """
        try:
            click.echo(f"Stopping container '{container_identifier}'...")

            request = dockyard_pb2.StopRequest(
                container_identifier=container_identifier,
                force=force,
                timeout=timeout
            )

            response = self.client.stub.StopContainer(request)

            if response.success:
                click.echo(f"Success: {response.message}")
            else:
                click.echo(f"Failed: {response.message}", err=True)
                sys.exit(1)

        except Exception as e:
            self.handle_error(e)

    def ps(self, all=False):
        """List containers

        Args:
            all: Show all containers (including stopped)
        """
        try:
            request = dockyard_pb2.ListContainersRequest(all=all)
            response = self.client.stub.ListContainers(request)

            if not response.success:
                click.echo(f"Failed: {response.message}", err=True)
                sys.exit(1)

            if not response.containers:
                click.echo("No containers found")
                return

            # Format as table
            headers = ["CONTAINER ID", "IMAGE", "COMMAND", "CREATED", "STATUS", "PORTS", "NAMES"]
            rows = []

            for container in response.containers:
                rows.append([
                    container.id,
                    container.image,
                    container.command,
                    container.created,
                    container.status,
                    container.ports,
                    container.names
                ])

            print_table(headers, rows)

        except Exception as e:
            self.handle_error(e)

    def inspect(self, container_identifier):
        """Inspect container

        Args:
            container_identifier: Container name or ID
        """
        try:
            request = dockyard_pb2.InspectContainerRequest(
                container_identifier=container_identifier
            )

            response = self.client.stub.InspectContainer(request)

            if response.success:
                click.echo(response.json_data)
            else:
                click.echo(f"Failed: {response.message}", err=True)
                sys.exit(1)

        except Exception as e:
            self.handle_error(e)

    def rm(self, container_identifiers, force=False, volumes=False):
        """Remove containers

        Args:
            container_identifiers: List of container names/IDs
            force: Force remove running containers
            volumes: Remove associated volumes
        """
        try:
            success_count = 0
            fail_count = 0

            for container_id in container_identifiers:
                click.echo(f"Removing container '{container_id}'...")

                request = dockyard_pb2.RemoveContainerRequest(
                    container_identifier=container_id,
                    force=force
                )

                response = self.client.stub.RemoveContainer(request)

                if response.success:
                    click.echo(f"Success: {response.message}")
                    click.echo(f"Container ID: {response.container_id}")
                    success_count += 1
                else:
                    click.echo(f"Failed: {response.message}", err=True)
                    fail_count += 1

            # Summary
            if len(container_identifiers) > 1:
                click.echo(f"\nSummary: {success_count} removed, {fail_count} failed")

            if fail_count > 0:
                sys.exit(1)

        except Exception as e:
            self.handle_error(e)
