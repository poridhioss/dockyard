#!/usr/bin/env python3
import sys
import os
import grpc
import docker
import yaml
import logging
import threading
import queue
from concurrent import futures
from pathlib import Path

# Add parent directory to path for proto imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import dockyard_pb2
import dockyard_pb2_grpc

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DockyardServicer(dockyard_pb2_grpc.DockyardServiceServicer):
    def __init__(self):
        try:
            # Use docker.from_env() which properly handles socket connection
            self.docker_client = docker.from_env()
            logger.info("Connected to Docker daemon")
        except Exception as e:
            logger.error(f"Failed to connect to Docker: {e}")
            raise

    def LaunchContainer(self, request, context):
        try:
            container_config = {}

            # Handle config file if provided
            if request.config_file:
                config_path = Path(request.config_file)
                if config_path.exists():
                    with open(config_path, 'r') as f:
                        config = yaml.safe_load(f)
                        container_config = self._parse_config(config)
                else:
                    return dockyard_pb2.LaunchResponse(
                        success=False,
                        message=f"Config file not found: {request.config_file}"
                    )

            # Basic configuration
            image = request.image or container_config.get('image')
            if not image:
                return dockyard_pb2.LaunchResponse(
                    success=False,
                    message="No image specified"
                )

            name = request.name or container_config.get('name')

            # Pull image if not exists
            try:
                self.docker_client.images.get(image)
                logger.info(f"Image {image} already exists")
            except docker.errors.ImageNotFound:
                logger.info(f"Pulling image {image}...")
                self.docker_client.images.pull(image)

            # Launch container
            container_args = {
                'image': image,
                'detach': True,
                'auto_remove': False
            }

            if name:
                container_args['name'] = name

            # Apply config file settings if available
            if container_config:
                if 'environment' in container_config:
                    container_args['environment'] = container_config['environment']
                if 'ports' in container_config:
                    container_args['ports'] = container_config['ports']
                if 'volumes' in container_config:
                    container_args['volumes'] = container_config['volumes']

            container = self.docker_client.containers.run(**container_args)

            logger.info(f"Container launched: {container.id[:12]}")
            return dockyard_pb2.LaunchResponse(
                success=True,
                container_id=container.id[:12],
                message=f"Container {name or container.id[:12]} launched successfully"
            )

        except docker.errors.APIError as e:
            logger.error(f"Docker API error: {e}")
            return dockyard_pb2.LaunchResponse(
                success=False,
                message=f"Docker error: {str(e)}"
            )
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return dockyard_pb2.LaunchResponse(
                success=False,
                message=f"Error: {str(e)}"
            )

    def StopContainer(self, request, context):
        try:
            container_identifier = request.container_identifier
            force = request.force
            timeout = request.timeout if request.timeout > 0 else 10

            if not container_identifier:
                return dockyard_pb2.StopResponse(
                    success=False,
                    message="Container identifier (name or ID) is required"
                )

            # Find container by name or ID
            try:
                container = self.docker_client.containers.get(container_identifier)
            except docker.errors.NotFound:
                return dockyard_pb2.StopResponse(
                    success=False,
                    message=f"Container '{container_identifier}' not found"
                )

            # Check if container is already stopped
            container.reload()
            if container.status in ['exited', 'stopped']:
                return dockyard_pb2.StopResponse(
                    success=True,
                    container_id=container.id[:12],
                    message=f"Container '{container_identifier}' is already stopped"
                )

            # Stop the container
            if force:
                logger.info(f"Force stopping container: {container.id[:12]}")
                container.kill()
            else:
                logger.info(f"Gracefully stopping container: {container.id[:12]} (timeout: {timeout}s)")
                container.stop(timeout=timeout)

            logger.info(f"Container stopped: {container.id[:12]}")
            return dockyard_pb2.StopResponse(
                success=True,
                container_id=container.id[:12],
                message=f"Container '{container_identifier}' stopped successfully"
            )

        except docker.errors.APIError as e:
            logger.error(f"Docker API error: {e}")
            return dockyard_pb2.StopResponse(
                success=False,
                message=f"Docker error: {str(e)}"
            )
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return dockyard_pb2.StopResponse(
                success=False,
                message=f"Error: {str(e)}"
            )

    def ExecContainer(self, request_iterator, context):
        """Execute commands in a container with bidirectional streaming"""
        try:
            # Get the first request (should be ExecStart)
            first_request = next(request_iterator)

            if not first_request.HasField('start'):
                yield dockyard_pb2.ExecResponse(
                    status=dockyard_pb2.ExecStatus(
                        success=False,
                        message="First request must be ExecStart"
                    )
                )
                return

            exec_start = first_request.start
            container_identifier = exec_start.container_identifier
            command = list(exec_start.command)
            interactive = exec_start.interactive
            user = exec_start.user if exec_start.user else None
            working_dir = exec_start.working_dir if exec_start.working_dir else None
            environment = dict(exec_start.environment) if exec_start.environment else None

            if not command:
                yield dockyard_pb2.ExecResponse(
                    status=dockyard_pb2.ExecStatus(
                        success=False,
                        message="Command is required"
                    )
                )
                return

            # Find the container
            try:
                container = self.docker_client.containers.get(container_identifier)
            except docker.errors.NotFound:
                yield dockyard_pb2.ExecResponse(
                    status=dockyard_pb2.ExecStatus(
                        success=False,
                        message=f"Container '{container_identifier}' not found"
                    )
                )
                return

            # Check if container is running
            container.reload()
            if container.status != 'running':
                yield dockyard_pb2.ExecResponse(
                    status=dockyard_pb2.ExecStatus(
                        success=False,
                        message=f"Container '{container_identifier}' is not running (status: {container.status})"
                    )
                )
                return

            # Create exec instance
            exec_config = {
                'cmd': command,
                'stdout': True,
                'stderr': True,
                'stdin': True,
                'tty': interactive,
            }

            if user:
                exec_config['user'] = user
            if working_dir:
                exec_config['workdir'] = working_dir
            if environment:
                exec_config['environment'] = environment

            exec_instance = self.docker_client.api.exec_create(
                container.id,
                **exec_config
            )
            exec_id = exec_instance['Id']

            logger.info(f"Created exec instance {exec_id[:12]} in container {container.id[:12]}")

            # Start execution
            exec_socket = self.docker_client.api.exec_start(
                exec_id,
                detach=False,
                tty=interactive,
                stream=True,
                socket=True
            )

            # Send initial success status
            yield dockyard_pb2.ExecResponse(
                status=dockyard_pb2.ExecStatus(
                    success=True,
                    exec_id=exec_id[:12],
                    message="Execution started successfully"
                )
            )

            # Create queues for communication
            input_queue = queue.Queue()
            output_queue = queue.Queue()

            # Thread to handle stdin from client
            def handle_input():
                try:
                    for request in request_iterator:
                        if request.HasField('input'):
                            input_data = request.input.data
                            if input_data:
                                exec_socket._sock.send(input_data)
                except Exception as e:
                    logger.error(f"Input handling error: {e}")
                finally:
                    # Close the socket when no more input
                    try:
                        exec_socket._sock.shutdown(1)  # Shutdown write side
                    except:
                        pass

            # Thread to handle stdout/stderr from container
            def handle_output():
                try:
                    while True:
                        try:
                            # Receive data from exec socket
                            data = exec_socket._sock.recv(4096)
                            if not data:
                                break

                            # For TTY mode, all output comes as stdout
                            # For non-TTY mode, Docker multiplexes stdout/stderr
                            if interactive:
                                output_queue.put(('stdout', data))
                            else:
                                # Parse Docker's stream format for stdout/stderr separation
                                if len(data) >= 8:
                                    stream_type = data[0]  # 1=stdout, 2=stderr
                                    size = int.from_bytes(data[4:8], 'big')
                                    payload = data[8:8+size] if size <= len(data)-8 else data[8:]

                                    stream_name = 'stdout' if stream_type == 1 else 'stderr'
                                    output_queue.put((stream_name, payload))
                                else:
                                    # Fallback for malformed data
                                    output_queue.put(('stdout', data))

                        except Exception as e:
                            logger.error(f"Output handling error: {e}")
                            break

                    output_queue.put((None, None))  # Signal end
                except Exception as e:
                    logger.error(f"Output thread error: {e}")
                    output_queue.put((None, None))

            # Start threads
            input_thread = threading.Thread(target=handle_input)
            output_thread = threading.Thread(target=handle_output)

            input_thread.daemon = True
            output_thread.daemon = True

            input_thread.start()
            output_thread.start()

            # Send output to client
            try:
                while True:
                    try:
                        stream_type, data = output_queue.get(timeout=1)
                        if stream_type is None:  # End signal
                            break

                        if data:
                            yield dockyard_pb2.ExecResponse(
                                output=dockyard_pb2.ExecOutput(
                                    data=data,
                                    stream_type=stream_type
                                )
                            )
                    except queue.Empty:
                        # Check if exec is still running
                        try:
                            exec_info = self.docker_client.api.exec_inspect(exec_id)
                            if not exec_info.get('Running', True):
                                break
                        except:
                            break
                        continue

            except Exception as e:
                logger.error(f"Output streaming error: {e}")

            # Get final execution result
            try:
                exec_info = self.docker_client.api.exec_inspect(exec_id)
                exit_code = exec_info.get('ExitCode', 0)

                yield dockyard_pb2.ExecResponse(
                    status=dockyard_pb2.ExecStatus(
                        success=True,
                        exec_id=exec_id[:12],
                        message="Execution completed",
                        exit_code=exit_code,
                        finished=True
                    )
                )

                logger.info(f"Exec {exec_id[:12]} completed with exit code {exit_code}")

            except Exception as e:
                logger.error(f"Failed to get exec result: {e}")
                yield dockyard_pb2.ExecResponse(
                    status=dockyard_pb2.ExecStatus(
                        success=False,
                        exec_id=exec_id[:12],
                        message=f"Failed to get execution result: {str(e)}",
                        finished=True
                    )
                )

            # Cleanup
            try:
                exec_socket.close()
            except:
                pass

        except Exception as e:
            logger.error(f"ExecContainer error: {e}")
            yield dockyard_pb2.ExecResponse(
                status=dockyard_pb2.ExecStatus(
                    success=False,
                    message=f"Execution failed: {str(e)}"
                )
            )

    def _parse_config(self, config):
        """Parse YAML config file for container settings"""
        result = {}
        if 'image' in config:
            result['image'] = config['image']
        if 'name' in config:
            result['name'] = config['name']
        if 'environment' in config:
            result['environment'] = config['environment']
        if 'ports' in config:
            result['ports'] = config['ports']
        if 'volumes' in config:
            result['volumes'] = config['volumes']
        return result


def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    dockyard_pb2_grpc.add_DockyardServiceServicer_to_server(
        DockyardServicer(), server
    )

    # Listen on all interfaces for EC2 access
    server.add_insecure_port('[::]:50051')
    server.start()
    logger.info("Agent started on port 50051")

    try:
        server.wait_for_termination()
    except KeyboardInterrupt:
        logger.info("Shutting down agent...")
        server.stop(0)


if __name__ == '__main__':
    serve()