"""
Exec service for Dockyard Agent
Handles container exec operations with bidirectional streaming
"""
import queue
import threading
from typing import Iterator, Any
from agent.utils.logger import get_logger
from agent.utils.exceptions import ContainerNotFoundException, ContainerOperationException

logger = get_logger(__name__)


class ExecService:
    """Service for container exec operations"""

    def __init__(self, docker_client):
        """Initialize exec service

        Args:
            docker_client: DockerClientWrapper instance
        """
        self.docker_client = docker_client.client

    def execute_command(
        self,
        container_identifier: str,
        command: list,
        interactive: bool = False,
        user: str = None,
        working_dir: str = None,
        environment: dict = None,
        input_iterator: Iterator[Any] = None
    ) -> Iterator[dict]:
        """Execute command in container with streaming support

        Args:
            container_identifier: Container name or ID
            command: Command and arguments to execute
            interactive: Enable interactive mode (TTY)
            user: User to run command as
            working_dir: Working directory
            environment: Environment variables
            input_iterator: Iterator for stdin input (for interactive mode)

        Yields:
            Dictionary with stdout, stderr, and exit_code
        """
        try:
            container = self.docker_client.containers.get(container_identifier)
            logger.info(f"Executing command in container {container_identifier}: {' '.join(command)}")

            if interactive and input_iterator:
                # Interactive mode with bidirectional streaming
                yield from self._execute_interactive(
                    container, command, user, working_dir, environment, input_iterator
                )
            else:
                # Non-interactive mode
                yield from self._execute_simple(
                    container, command, user, working_dir, environment
                )

        except Exception as e:
            logger.error(f"Failed to execute command: {e}")
            yield {
                'stdout': b'',
                'stderr': str(e).encode(),
                'exit_code': -1
            }

    def _execute_simple(
        self,
        container,
        command: list,
        user: str,
        working_dir: str,
        environment: dict
    ) -> Iterator[dict]:
        """Execute command in non-interactive mode

        Args:
            container: Docker container object
            command: Command and arguments
            user: User to run as
            working_dir: Working directory
            environment: Environment variables

        Yields:
            Output dictionary
        """
        try:
            exec_result = container.exec_run(
                cmd=command,
                stdout=True,
                stderr=True,
                stdin=False,
                tty=False,
                privileged=False,
                user=user or '',
                environment=environment or {},
                workdir=working_dir or '',
                detach=False,
                stream=True,
                socket=False,
                demux=True
            )

            # Stream output
            for stdout_chunk, stderr_chunk in exec_result.output:
                yield {
                    'stdout': stdout_chunk or b'',
                    'stderr': stderr_chunk or b'',
                    'exit_code': None
                }

            # Get exit code
            exit_code = exec_result.exit_code
            logger.info(f"Command completed with exit code: {exit_code}")

            yield {
                'stdout': b'',
                'stderr': b'',
                'exit_code': exit_code
            }

        except Exception as e:
            logger.error(f"Exec failed: {e}")
            yield {
                'stdout': b'',
                'stderr': str(e).encode(),
                'exit_code': -1
            }

    def _execute_interactive(
        self,
        container,
        command: list,
        user: str,
        working_dir: str,
        environment: dict,
        input_iterator: Iterator[Any]
    ) -> Iterator[dict]:
        """Execute command in interactive mode with stdin support

        Args:
            container: Docker container object
            command: Command and arguments
            user: User to run as
            working_dir: Working directory
            environment: Environment variables
            input_iterator: Iterator providing stdin input

        Yields:
            Output dictionary
        """
        try:
            # Create exec instance
            exec_id = self.docker_client.api.exec_create(
                container.id,
                cmd=command,
                stdout=True,
                stderr=True,
                stdin=True,
                tty=True,
                privileged=False,
                user=user or '',
                environment=environment or {},
                workdir=working_dir or ''
            )

            # Start exec with socket
            sock = self.docker_client.api.exec_start(
                exec_id['Id'],
                detach=False,
                tty=True,
                stream=True,
                socket=True,
                demux=False
            )

            # Queue for output
            output_queue = queue.Queue()
            stop_event = threading.Event()

            # Thread to read output from socket
            def read_output():
                try:
                    while not stop_event.is_set():
                        try:
                            data = sock._sock.recv(4096)
                            if not data:
                                break
                            output_queue.put(('output', data))
                        except Exception as e:
                            if not stop_event.is_set():
                                logger.error(f"Error reading output: {e}")
                            break
                except Exception as e:
                    logger.error(f"Output thread error: {e}")
                finally:
                    output_queue.put(('done', None))

            # Thread to write input to socket
            def write_input():
                try:
                    for input_data in input_iterator:
                        if stop_event.is_set():
                            break
                        if input_data:
                            sock._sock.sendall(input_data)
                except Exception as e:
                    logger.error(f"Error writing input: {e}")

            # Start threads
            output_thread = threading.Thread(target=read_output, daemon=True)
            input_thread = threading.Thread(target=write_input, daemon=True)

            output_thread.start()
            input_thread.start()

            # Yield output as it comes
            while True:
                try:
                    msg_type, data = output_queue.get(timeout=1)
                    if msg_type == 'done':
                        break
                    elif msg_type == 'output':
                        yield {
                            'stdout': data,
                            'stderr': b'',
                            'exit_code': None
                        }
                except queue.Empty:
                    continue

            # Stop threads
            stop_event.set()

            # Get exit code
            inspect = self.docker_client.api.exec_inspect(exec_id['Id'])
            exit_code = inspect.get('ExitCode', 0)

            logger.info(f"Interactive exec completed with exit code: {exit_code}")

            yield {
                'stdout': b'',
                'stderr': b'',
                'exit_code': exit_code
            }

            # Close socket
            try:
                sock.close()
            except:
                pass

        except Exception as e:
            logger.error(f"Interactive exec failed: {e}")
            yield {
                'stdout': b'',
                'stderr': str(e).encode(),
                'exit_code': -1
            }
