#!/usr/bin/env python3
import sys
import os
import click
import grpc
import yaml
import threading
import time
from pathlib import Path

# Platform-specific imports
try:
    import select
    import tty
    import termios
    HAS_TERMIOS = True
except ImportError:
    HAS_TERMIOS = False

try:
    import msvcrt
    HAS_MSVCRT = True
except ImportError:
    HAS_MSVCRT = False

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

    def exec_container(self, container_identifier, command, interactive=False, user=None, working_dir=None, environment=None):
        """Execute a command in a container with streaming support"""
        try:
            def generate_requests():
                # Send initial ExecStart request
                exec_start = dockyard_pb2.ExecStart(
                    container_identifier=container_identifier,
                    command=command,
                    interactive=interactive,
                    user=user or '',
                    working_dir=working_dir or '',
                    environment=environment or {}
                )

                yield dockyard_pb2.ExecRequest(start=exec_start)

                # For interactive mode, handle stdin input
                if interactive:
                    # Set up raw terminal mode for interactive input
                    old_settings = None
                    try:
                        if HAS_TERMIOS:
                            old_settings = termios.tcgetattr(sys.stdin.fileno())
                            tty.setraw(sys.stdin.fileno())
                    except:
                        pass  # Not a TTY

                    try:
                        while True:
                            # Use platform-specific input handling
                            if HAS_TERMIOS and sys.platform != 'win32':
                                # Unix/Linux
                                ready, _, _ = select.select([sys.stdin], [], [], 0.1)
                                if ready:
                                    data = sys.stdin.read(1).encode('utf-8')
                                    if data:
                                        yield dockyard_pb2.ExecRequest(
                                            input=dockyard_pb2.ExecInput(data=data)
                                        )
                            elif HAS_MSVCRT:
                                # Windows
                                if msvcrt.kbhit():
                                    data = msvcrt.getch()
                                    if data:
                                        yield dockyard_pb2.ExecRequest(
                                            input=dockyard_pb2.ExecInput(data=data)
                                        )
                                else:
                                    time.sleep(0.1)  # Prevent busy waiting
                            else:
                                # Fallback for unsupported platforms
                                time.sleep(0.1)
                    except KeyboardInterrupt:
                        # Send Ctrl+C to container
                        yield dockyard_pb2.ExecRequest(
                            input=dockyard_pb2.ExecInput(data=b'\x03')
                        )
                    finally:
                        # Restore terminal settings
                        if old_settings and HAS_TERMIOS:
                            try:
                                termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, old_settings)
                            except:
                                pass

            # Start streaming
            response_stream = self.stub.ExecContainer(generate_requests())
            return response_stream

        except grpc.RpcError as e:
            click.echo(f"Error: Failed to connect to agent - {e.details()}", err=True)
            return None

    def get_logs(self, container_identifier, follow=False, tail=0, since=None, timestamps=False, stdout=True, stderr=True):
        """Get container logs with streaming support"""
        request = dockyard_pb2.LogsRequest(
            container_identifier=container_identifier,
            follow=follow,
            tail=tail,
            since=since or '',
            timestamps=timestamps,
            stdout=stdout,
            stderr=stderr
        )

        try:
            response_stream = self.stub.GetLogs(request)
            return response_stream
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


@cli.command(context_settings={"ignore_unknown_options": True})
@click.argument('container', required=True)
@click.argument('command', nargs=-1, required=False)
@click.option('--interactive', '-i', is_flag=True, help='Run in interactive mode (allocate TTY)')
@click.option('--user', '-u', help='Run as specified user')
@click.option('--workdir', '-w', help='Working directory inside container')
@click.option('--env', '-e', multiple=True, help='Set environment variables (KEY=VALUE)')
@click.pass_context
def exec(ctx, container, command, interactive, user, workdir, env):
    """Execute commands in a running container

    Examples:
        dockyard exec web-server ls -la
        dockyard exec --interactive web-server bash
        dockyard exec --user root web-server "apt update"
        dockyard exec --env "DEBUG=true" web-server python script.py
    """
    client = ctx.obj['client']

    # Parse command
    if not command and not interactive:
        click.echo("Error: Command is required unless using --interactive mode", err=True)
        sys.exit(1)

    # If interactive and no command, default to shell
    if interactive and not command:
        command = ['bash']  # Default to bash for interactive
    elif command:
        command = list(command)
    else:
        command = []

    # Parse environment variables
    environment = {}
    for env_var in env:
        if '=' in env_var:
            key, value = env_var.split('=', 1)
            environment[key] = value
        else:
            click.echo(f"Warning: Invalid environment variable format: {env_var}", err=True)

    click.echo(f"Executing {'interactive ' if interactive else ''}command in container '{container}'...")
    if command:
        click.echo(f"Command: {' '.join(command)}")

    try:
        # Get response stream
        response_stream = client.exec_container(
            container_identifier=container,
            command=command,
            interactive=interactive,
            user=user,
            working_dir=workdir,
            environment=environment
        )

        if not response_stream:
            sys.exit(1)

        exit_code = 0
        exec_started = False

        # Handle responses
        for response in response_stream:
            if response.HasField('status'):
                status = response.status
                if not status.success:
                    click.echo(f"Error: {status.message}", err=True)
                    sys.exit(1)

                if status.finished:
                    exit_code = status.exit_code
                    if not exec_started:
                        # Only show completion message if we haven't shown any output
                        click.echo(f"Command completed with exit code {exit_code}")
                    break
                elif not exec_started:
                    exec_started = True

            elif response.HasField('output'):
                output = response.output
                data = output.data

                # Write output directly to stdout/stderr
                if output.stream_type == 'stderr':
                    sys.stderr.buffer.write(data)
                    sys.stderr.buffer.flush()
                else:
                    sys.stdout.buffer.write(data)
                    sys.stdout.buffer.flush()

        client.close()

        # Exit with the same code as the command
        if exit_code != 0:
            sys.exit(exit_code)

    except KeyboardInterrupt:
        click.echo("\nExecution interrupted by user")
        client.close()
        sys.exit(130)  # Standard exit code for Ctrl+C
    except Exception as e:
        click.echo(f"Unexpected error: {e}", err=True)
        client.close()
        sys.exit(1)


@cli.command()
@click.argument('container', required=True)
@click.option('--follow', '-f', is_flag=True, help='Follow log output (like tail -f)')
@click.option('--tail', '-n', default=0, help='Number of lines from end (0 = all)')
@click.option('--since', help='Show logs since relative time (e.g., 1h, 30m, 10s)')
@click.option('--timestamps', '-t', is_flag=True, help='Show timestamps')
@click.option('--no-stdout', is_flag=True, help='Do not include stdout')
@click.option('--no-stderr', is_flag=True, help='Do not include stderr')
@click.pass_context
def logs(ctx, container, follow, tail, since, timestamps, no_stdout, no_stderr):
    """View container logs

    Examples:
        dockyard logs web-server
        dockyard logs -f web-server
        dockyard logs --tail 100 web-server
        dockyard logs --since 1h web-server
        dockyard logs -f -t web-server
    """
    client = ctx.obj['client']

    # Determine which streams to include
    stdout = not no_stdout
    stderr = not no_stderr

    if not stdout and not stderr:
        click.echo("Error: Cannot exclude both stdout and stderr", err=True)
        sys.exit(1)

    # Validate tail option
    if tail < 0:
        click.echo("Error: Tail value must be non-negative", err=True)
        sys.exit(1)

    # Validate since format if provided
    if since:
        import re
        if not re.match(r'^\d+[smhd]$', since):
            click.echo("Error: Invalid since format. Use format like '1h', '30m', '10s', '7d'", err=True)
            sys.exit(1)

    click.echo(f"{'Following' if follow else 'Getting'} logs for container '{container}'...")

    if tail > 0:
        click.echo(f"Showing last {tail} lines")
    if since:
        click.echo(f"Logs since {since} ago")

    try:
        # Get response stream
        response_stream = client.get_logs(
            container_identifier=container,
            follow=follow,
            tail=tail,
            since=since,
            timestamps=timestamps,
            stdout=stdout,
            stderr=stderr
        )

        if not response_stream:
            sys.exit(1)

        # Handle responses
        for response in response_stream:
            if response.HasField('status'):
                status = response.status
                if not status.success:
                    click.echo(f"Error: {status.message}", err=True)
                    sys.exit(1)

                if status.finished:
                    # Non-follow mode completed
                    break

            elif response.HasField('log'):
                log_entry = response.log
                data = log_entry.data

                # Format output with optional coloring for stderr
                if log_entry.stream_type == 'stderr':
                    # Output to stderr
                    if timestamps and log_entry.timestamp:
                        sys.stderr.buffer.write(f"{log_entry.timestamp} ".encode('utf-8'))
                    sys.stderr.buffer.write(data)
                    sys.stderr.buffer.flush()
                else:
                    # Output to stdout
                    if timestamps and log_entry.timestamp:
                        sys.stdout.buffer.write(f"{log_entry.timestamp} ".encode('utf-8'))
                    sys.stdout.buffer.write(data)
                    sys.stdout.buffer.flush()

        client.close()

    except KeyboardInterrupt:
        click.echo("\nLog streaming interrupted by user")
        client.close()
        sys.exit(130)  # Standard exit code for Ctrl+C
    except Exception as e:
        click.echo(f"Unexpected error: {e}", err=True)
        client.close()
        sys.exit(1)


if __name__ == '__main__':
    cli()