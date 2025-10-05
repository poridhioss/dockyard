"""
Exec command for Dockyard CLI
"""
import sys
import os
import click
import threading

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import dockyard_pb2

from cli.commands.base import BaseCommand


class ExecCommand(BaseCommand):
    """Exec command implementation"""

    def execute(self, container_identifier, command, interactive=False, user=None,
                working_dir=None, environment=None):
        """Execute command in container

        Args:
            container_identifier: Container name or ID
            command: Command to execute
            interactive: Interactive mode
            user: User to run as
            working_dir: Working directory
            environment: Environment variables dict
        """
        try:
            if interactive:
                self._execute_interactive(container_identifier, command, user, working_dir, environment)
            else:
                self._execute_simple(container_identifier, command, user, working_dir, environment)

        except KeyboardInterrupt:
            click.echo("\nExecution interrupted", err=True)
            sys.exit(130)
        except Exception as e:
            self.handle_error(e)

    def _execute_simple(self, container_identifier, command, user, working_dir, environment):
        """Execute command in non-interactive mode"""
        # Create exec start request
        start = dockyard_pb2.ExecStart(
            container_identifier=container_identifier,
            command=command,
            interactive=False,
            user=user or '',
            working_dir=working_dir or '',
            environment=environment or {}
        )

        # Create request iterator
        def request_iterator():
            yield dockyard_pb2.ExecRequest(start=start)

        # Execute
        for response in self.client.stub.ExecContainer(request_iterator()):
            if response.HasField('status'):
                if not response.status.success:
                    click.echo(f"Error: {response.status.message}", err=True)
                    sys.exit(1)
                elif response.status.finished:
                    sys.exit(response.status.exit_code)
            elif response.HasField('output'):
                if response.output.data:
                    if response.output.stream_type == "stdout":
                        sys.stdout.buffer.write(response.output.data)
                        sys.stdout.flush()
                    else:
                        sys.stderr.buffer.write(response.output.data)
                        sys.stderr.flush()

    def _execute_interactive(self, container_identifier, command, user, working_dir, environment):
        """Execute command in interactive mode with stdin support"""
        import queue

        # Create exec start request
        start = dockyard_pb2.ExecStart(
            container_identifier=container_identifier,
            command=command,
            interactive=True,
            user=user or '',
            working_dir=working_dir or '',
            environment=environment or {}
        )

        # Queue for stdin input
        input_queue = queue.Queue()
        stop_event = threading.Event()

        # Thread to read stdin
        def read_stdin():
            try:
                while not stop_event.is_set():
                    try:
                        data = sys.stdin.buffer.read(1024)
                        if data:
                            input_queue.put(data)
                        else:
                            break
                    except Exception:
                        break
            except Exception:
                pass

        # Start stdin reader thread
        stdin_thread = threading.Thread(target=read_stdin, daemon=True)
        stdin_thread.start()

        # Create request iterator
        def request_iterator():
            # Send start request
            yield dockyard_pb2.ExecRequest(start=start)

            # Send input from queue
            while not stop_event.is_set():
                try:
                    data = input_queue.get(timeout=0.1)
                    yield dockyard_pb2.ExecRequest(
                        input=dockyard_pb2.ExecInput(data=data)
                    )
                except queue.Empty:
                    continue
                except Exception:
                    break

        # Execute
        try:
            for response in self.client.stub.ExecContainer(request_iterator()):
                if response.HasField('status'):
                    if not response.status.success:
                        click.echo(f"Error: {response.status.message}", err=True)
                        stop_event.set()
                        sys.exit(1)
                    elif response.status.finished:
                        stop_event.set()
                        sys.exit(response.status.exit_code)
                elif response.HasField('output'):
                    if response.output.data:
                        if response.output.stream_type == "stdout":
                            sys.stdout.buffer.write(response.output.data)
                            sys.stdout.flush()
                        else:
                            sys.stderr.buffer.write(response.output.data)
                            sys.stderr.flush()
        finally:
            stop_event.set()
