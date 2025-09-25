#!/usr/bin/env python3
import sys
import os
import click
import grpc
import yaml
from pathlib import Path

# Add parent directory to path for proto imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import dockyard_pb2
import dockyard_pb2_grpc


class DockyardClient:
    def __init__(self, host='localhost', port=50051):
        self.channel = grpc.insecure_channel(f'{host}:{port}')
        self.stub = dockyard_pb2_grpc.DockyardServiceStub(self.channel)

    def launch_container(self, image=None, name=None, config_file=None):
        request = dockyard_pb2.LaunchRequest(
            image=image or '',
            name=name or '',
            config_file=config_file or ''
        )

        try:
            response = self.stub.LaunchContainer(request)
            return response
        except grpc.RpcError as e:
            click.echo(f"Error: Failed to connect to agent - {e.details()}", err=True)
            return None

    def stop_container(self, container_identifier, force=False, timeout=10):
        request = dockyard_pb2.StopRequest(
            container_identifier=container_identifier,
            force=force,
            timeout=timeout
        )

        try:
            response = self.stub.StopContainer(request)
            return response
        except grpc.RpcError as e:
            click.echo(f"Error: Failed to connect to agent - {e.details()}", err=True)
            return None

    def close(self):
        self.channel.close()


@click.group()
@click.option('--host', default='localhost', envvar='DOCKYARD_HOST',
              help='Agent host address')
@click.option('--port', default=50051, envvar='DOCKYARD_PORT',
              help='Agent port')
@click.pass_context
def cli(ctx, host, port):
    """Dockyard - Container orchestration CLI"""
    ctx.ensure_object(dict)
    ctx.obj['client'] = DockyardClient(host, port)


@cli.command()
@click.argument('image', required=False)
@click.option('--name', '-n', help='Container name')
@click.option('-f', '--file', 'config_file', help='YAML config file')
@click.pass_context
def launch(ctx, image, name, config_file):
    """Launch a container

    Examples:
        dockyard launch nginx:latest
        dockyard launch redis:alpine --name cache
        dockyard launch -f app.yaml
    """
    client = ctx.obj['client']

    # Validate inputs
    if not image and not config_file:
        click.echo("Error: Either provide an image or a config file (-f)", err=True)
        sys.exit(1)

    if config_file and not Path(config_file).exists():
        click.echo(f"Error: Config file not found: {config_file}", err=True)
        sys.exit(1)

    # Launch container
    click.echo(f"Launching container...")
    response = client.launch_container(
        image=image,
        name=name,
        config_file=config_file
    )

    if response:
        if response.success:
            click.echo(f"Success: {response.message}")
            if response.container_id:
                click.echo(f"Container ID: {response.container_id}")
        else:
            click.echo(f"Failed: {response.message}", err=True)
            sys.exit(1)

    client.close()


@cli.command()
@click.argument('containers', nargs=-1, required=True)
@click.option('--force', '-f', is_flag=True, help='Force stop (kill instead of graceful stop)')
@click.option('--timeout', '-t', default=10, help='Timeout in seconds for graceful stop (default: 10)')
@click.pass_context
def stop(ctx, containers, force, timeout):
    """Stop one or more containers

    Examples:
        dockyard stop web-server
        dockyard stop nginx redis
        dockyard stop --force web-server
        dockyard stop --timeout 30 web-server
    """
    client = ctx.obj['client']

    # Handle multiple containers
    failed_containers = []
    stopped_containers = []

    for container in containers:
        click.echo(f"Stopping container '{container}'...")

        response = client.stop_container(
            container_identifier=container,
            force=force,
            timeout=timeout
        )

        if response:
            if response.success:
                click.echo(f"Success: {response.message}")
                stopped_containers.append(container)
                if response.container_id:
                    click.echo(f"Container ID: {response.container_id}")
            else:
                click.echo(f"Failed to stop '{container}': {response.message}", err=True)
                failed_containers.append(container)
        else:
            failed_containers.append(container)

    # Summary for batch operations
    if len(containers) > 1:
        click.echo(f"\nSummary: {len(stopped_containers)} stopped, {len(failed_containers)} failed")
        if failed_containers:
            click.echo(f"Failed containers: {', '.join(failed_containers)}", err=True)

    client.close()

    # Exit with error code if any containers failed to stop
    if failed_containers:
        sys.exit(1)


if __name__ == '__main__':
    cli()