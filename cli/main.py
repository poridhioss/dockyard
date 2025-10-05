#!/usr/bin/env python3
"""
Dockyard CLI - Main entry point
Refactored version with modular architecture
"""
import click
import sys

from cli.config import CLIConfig
from cli.client.grpc_client import DockyardClient
from cli.commands.container import ContainerCommands
from cli.commands.exec import ExecCommand
from cli.commands.logs import LogsCommand
from cli.commands.stats import StatsCommand
from cli.utils.exceptions import ConnectionException, AuthenticationException


# Global context
pass_config = click.make_pass_decorator(dict, ensure=True)


@click.group()
@click.option('--host', help='Agent hostname')
@click.option('--port', type=int, help='Agent port')
@click.pass_context
def cli(ctx, host, port):
    """Dockyard - Distributed Container Orchestration CLI"""
    # Load configuration
    config = CLIConfig()

    # Use provided options or fall back to config
    host = host or config.default_host
    port = port or config.default_port

    # Create client
    try:
        client = DockyardClient(host, port, timeout=config.timeout)
        ctx.obj = {
            'config': config,
            'client': client,
            'container_commands': ContainerCommands(client),
            'exec_command': ExecCommand(client),
            'logs_command': LogsCommand(client),
            'stats_command': StatsCommand(client)
        }
    except AuthenticationException as e:
        click.echo(f"Authentication error: {e}", err=True)
        click.echo("\nTo authenticate, set your token:", err=True)
        click.echo("  export DOCKYARD_AUTH_TOKEN='your-token'", err=True)
        click.echo("  or configure in ~/.dockyard/config.yaml", err=True)
        sys.exit(1)
    except ConnectionException as e:
        click.echo(f"Connection error: {e}", err=True)
        sys.exit(1)


# Container Management Commands

@cli.command()
@click.argument('image')
@click.option('--name', help='Container name')
@click.option('-f', '--config-file', help='YAML configuration file')
@pass_config
def launch(ctx, image, name, config_file):
    """Launch a new container"""
    ctx['container_commands'].launch(image, name, config_file)


@cli.command()
@click.argument('container_identifier')
@click.option('--force', is_flag=True, help='Force kill the container')
@click.option('--timeout', type=int, default=10, help='Timeout for graceful stop')
@pass_config
def stop(ctx, container_identifier, force, timeout):
    """Stop a container"""
    ctx['container_commands'].stop(container_identifier, force, timeout)


@cli.command()
@click.option('-a', '--all', is_flag=True, help='Show all containers (default shows just running)')
@pass_config
def ps(ctx, all):
    """List containers"""
    ctx['container_commands'].ps(all)


@cli.command()
@click.argument('container_identifier')
@pass_config
def inspect(ctx, container_identifier):
    """Inspect container details"""
    ctx['container_commands'].inspect(container_identifier)


@cli.command()
@click.argument('containers', nargs=-1, required=True)
@click.option('--force', is_flag=True, help='Force remove running containers')
@click.option('-v', '--volumes', is_flag=True, help='Remove associated volumes')
@pass_config
def rm(ctx, containers, force, volumes):
    """Remove one or more containers"""
    ctx['container_commands'].rm(list(containers), force, volumes)


# Exec Command

@cli.command()
@click.argument('container_identifier')
@click.argument('command', nargs=-1, required=True)
@click.option('-i', '--interactive', is_flag=True, help='Keep STDIN open and allocate TTY')
@click.option('--user', help='Username or UID')
@click.option('--workdir', help='Working directory')
@click.option('--env', multiple=True, help='Set environment variables')
@pass_config
def exec(ctx, container_identifier, command, interactive, user, workdir, env):
    """Execute a command in a running container"""
    # Parse environment variables
    environment = {}
    for e in env:
        if '=' in e:
            key, value = e.split('=', 1)
            environment[key] = value

    ctx['exec_command'].execute(
        container_identifier,
        list(command),
        interactive,
        user,
        workdir,
        environment
    )


# Logs Command

@cli.command()
@click.argument('container_identifier')
@click.option('-f', '--follow', is_flag=True, help='Follow log output')
@click.option('--tail', type=int, help='Number of lines to show from the end of the logs')
@click.option('--since', help='Show logs since timestamp (e.g. 2023-01-01T12:00:00) or relative (e.g. 1h, 30m)')
@click.option('--timestamps', is_flag=True, help='Show timestamps')
@click.option('--no-stdout', is_flag=True, help='Exclude stdout')
@click.option('--no-stderr', is_flag=True, help='Exclude stderr')
@pass_config
def logs(ctx, container_identifier, follow, tail, since, timestamps, no_stdout, no_stderr):
    """Fetch logs of a container"""
    ctx['logs_command'].get_logs(
        container_identifier,
        follow,
        tail,
        since,
        timestamps,
        no_stdout,
        no_stderr
    )


# Stats Command

@cli.command()
@click.argument('containers', nargs=-1)
@click.option('--no-stream', is_flag=True, help='Disable streaming stats and only pull the first result')
@pass_config
def stats(ctx, containers, no_stream):
    """Display a live stream of container(s) resource usage statistics"""
    ctx['stats_command'].get_stats(
        list(containers) if containers else None,
        no_stream
    )


# Config Command

@cli.group()
def config():
    """Manage CLI configuration"""
    pass


@config.command()
@click.argument('token')
def set_token(token):
    """Set authentication token"""
    from cli.auth.token_manager import TokenManager
    manager = TokenManager()
    manager.save_token(token)
    click.echo("Token saved successfully")


if __name__ == '__main__':
    cli()
