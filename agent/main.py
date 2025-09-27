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


    def GetLogs(self, request, context):
        """Stream container logs with optional following"""
        import datetime
        import re

        try:
            container_identifier = request.container_identifier
            follow = request.follow
            tail = request.tail if request.tail > 0 else "all"
            since = request.since
            timestamps = request.timestamps
            # Default to True for stdout and stderr unless explicitly set to False
            stdout = True if not hasattr(request, 'stdout') else request.stdout
            stderr = True if not hasattr(request, 'stderr') else request.stderr

            # Since proto3 defaults booleans to False, we need better logic
            # If both are False, default to showing both
            if not request.stdout and not request.stderr:
                stdout = True
                stderr = True

            logger.info(f"Getting logs for container: {container_identifier}, follow={follow}, tail={tail}, since={since}")

            # Find the container
            try:
                container = self.docker_client.containers.get(container_identifier)
            except docker.errors.NotFound:
                yield dockyard_pb2.LogsResponse(
                    status=dockyard_pb2.LogsStatus(
                        success=False,
                        message=f"Container '{container_identifier}' not found"
                    )
                )
                return

            # Parse the 'since' parameter to datetime if provided
            since_datetime = None
            if since:
                # Parse relative time format (e.g., "1h", "30m", "10s")
                match = re.match(r'^(\d+)([smhd])$', since)
                if match:
                    value, unit = match.groups()
                    value = int(value)

                    if unit == 's':
                        delta = datetime.timedelta(seconds=value)
                    elif unit == 'm':
                        delta = datetime.timedelta(minutes=value)
                    elif unit == 'h':
                        delta = datetime.timedelta(hours=value)
                    elif unit == 'd':
                        delta = datetime.timedelta(days=value)

                    since_datetime = datetime.datetime.utcnow() - delta
                    logger.info(f"Logs since: {since_datetime}")

            # Send initial success status
            yield dockyard_pb2.LogsResponse(
                status=dockyard_pb2.LogsStatus(
                    success=True,
                    message=f"Streaming logs for container '{container_identifier}'"
                )
            )

            try:
                # Get logs from Docker
                logs_generator = container.logs(
                    stdout=stdout,
                    stderr=stderr,
                    stream=True,
                    follow=follow,
                    tail=tail,
                    since=since_datetime,
                    timestamps=timestamps
                )

                # Stream logs to client
                for log_line in logs_generator:
                    if not log_line:
                        continue

                    # Parse Docker's stream format when both stdout and stderr are requested
                    if stdout and stderr and len(log_line) >= 8:
                        # Docker multiplexes stdout/stderr with 8-byte header
                        # Byte 0: stream type (1=stdout, 2=stderr)
                        # Bytes 1-3: reserved
                        # Bytes 4-7: size (big-endian)
                        stream_type = log_line[0]

                        # Check if this looks like a Docker stream header
                        if stream_type in [1, 2]:
                            try:
                                size = int.from_bytes(log_line[4:8], 'big')
                                if size <= len(log_line) - 8:
                                    payload = log_line[8:8+size]
                                    stream_name = 'stdout' if stream_type == 1 else 'stderr'
                                else:
                                    # Malformed header, treat as regular log
                                    payload = log_line
                                    stream_name = 'stdout'
                            except:
                                # Failed to parse, treat as regular log
                                payload = log_line
                                stream_name = 'stdout'
                        else:
                            # Not a Docker stream header, treat as regular log
                            payload = log_line
                            stream_name = 'stdout'
                    else:
                        # Single stream or couldn't parse header
                        payload = log_line
                        stream_name = 'stdout' if stdout else 'stderr'

                    # Extract timestamp if present (Docker format: "2024-01-01T00:00:00.000000000Z message")
                    timestamp_str = ""
                    if timestamps and payload:
                        # Docker timestamps are at the beginning of the line when timestamps=True
                        try:
                            # Decode payload to string to extract timestamp
                            decoded = payload.decode('utf-8', errors='replace')
                            # Look for ISO 8601 timestamp at the beginning
                            ts_match = re.match(r'^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+Z)\s+(.*)$', decoded)
                            if ts_match:
                                timestamp_str = ts_match.group(1)
                                # Remove timestamp from payload if we extracted it
                                payload = ts_match.group(2).encode('utf-8')
                        except:
                            pass

                    # Send log entry
                    yield dockyard_pb2.LogsResponse(
                        log=dockyard_pb2.LogEntry(
                            data=payload,
                            stream_type=stream_name,
                            timestamp=timestamp_str
                        )
                    )

                # Send finished status for non-follow mode
                if not follow:
                    yield dockyard_pb2.LogsResponse(
                        status=dockyard_pb2.LogsStatus(
                            success=True,
                            message="All logs retrieved",
                            finished=True
                        )
                    )

            except Exception as e:
                logger.error(f"Error streaming logs: {e}")
                yield dockyard_pb2.LogsResponse(
                    status=dockyard_pb2.LogsStatus(
                        success=False,
                        message=f"Error streaming logs: {str(e)}",
                        finished=True
                    )
                )

        except Exception as e:
            logger.error(f"GetLogs error: {e}")
            yield dockyard_pb2.LogsResponse(
                status=dockyard_pb2.LogsStatus(
                    success=False,
                    message=f"Internal error: {str(e)}",
                    finished=True
                )
            )


    def ListContainers(self, request, context):
        """List containers with optional showing of all (including stopped)"""
        try:
            # List containers - all=True includes stopped containers
            containers = self.docker_client.containers.list(all=request.all)

            container_infos = []
            for container in containers:
                try:
                    # Get container details
                    container.reload()

                    # Format creation time
                    created_time = container.attrs.get('Created', '')
                    if created_time:
                        # Convert from ISO format to human readable
                        from datetime import datetime
                        try:
                            dt = datetime.fromisoformat(created_time.replace('Z', '+00:00'))
                            created_time = dt.strftime('%Y-%m-%d %H:%M:%S')
                        except:
                            pass

                    # Get command
                    command = ' '.join(container.attrs.get('Config', {}).get('Cmd', []) or [])
                    if not command:
                        command = container.attrs.get('Config', {}).get('Entrypoint', [''])[0] or ''

                    # Format ports
                    ports_info = ""
                    if container.attrs.get('NetworkSettings', {}).get('Ports'):
                        port_mappings = []
                        for container_port, host_info in container.attrs['NetworkSettings']['Ports'].items():
                            if host_info:
                                for mapping in host_info:
                                    host_port = mapping.get('HostPort', '')
                                    if host_port:
                                        port_mappings.append(f"{host_port}:{container_port}")
                        ports_info = ', '.join(port_mappings)

                    container_info = dockyard_pb2.ContainerInfo(
                        id=container.id[:12],  # Short ID
                        image=container.image.tags[0] if container.image.tags else container.image.id[:12],
                        command=command[:50],  # Truncate long commands
                        created=created_time,
                        status=container.status,
                        ports=ports_info,
                        names=container.name
                    )
                    container_infos.append(container_info)

                except Exception as e:
                    logger.warning(f"Error processing container {container.id}: {e}")
                    continue

            logger.info(f"Listed {len(container_infos)} containers (all={request.all})")

            return dockyard_pb2.ListContainersResponse(
                success=True,
                containers=container_infos,
                message=f"Found {len(container_infos)} containers"
            )

        except Exception as e:
            logger.error(f"ListContainers error: {e}")
            return dockyard_pb2.ListContainersResponse(
                success=False,
                message=f"Error listing containers: {str(e)}"
            )

    def InspectContainer(self, request, context):
        """Get detailed container information as JSON"""
        try:
            container_identifier = request.container_identifier

            # Find the container
            try:
                container = self.docker_client.containers.get(container_identifier)
            except docker.errors.NotFound:
                return dockyard_pb2.InspectContainerResponse(
                    success=False,
                    message=f"Container '{container_identifier}' not found"
                )

            # Get full container inspection data
            container.reload()
            inspection_data = container.attrs

            # Convert to JSON string
            import json
            json_data = json.dumps(inspection_data, indent=2, default=str)

            logger.info(f"Inspected container: {container_identifier}")

            return dockyard_pb2.InspectContainerResponse(
                success=True,
                json_data=json_data,
                message=f"Container '{container_identifier}' inspection complete"
            )

        except Exception as e:
            logger.error(f"InspectContainer error: {e}")
            return dockyard_pb2.InspectContainerResponse(
                success=False,
                message=f"Error inspecting container: {str(e)}"
            )

    def RemoveContainer(self, request, context):
        """Remove a container with optional force"""
        try:
            container_identifier = request.container_identifier
            force = request.force

            # Find the container
            try:
                container = self.docker_client.containers.get(container_identifier)
            except docker.errors.NotFound:
                return dockyard_pb2.RemoveContainerResponse(
                    success=False,
                    message=f"Container '{container_identifier}' not found"
                )

            container_id = container.id[:12]
            container_name = container.name

            # Check if container is running and force is not specified
            container.reload()
            if container.status == 'running' and not force:
                return dockyard_pb2.RemoveContainerResponse(
                    success=False,
                    message=f"Container '{container_identifier}' is running. Use --force to remove."
                )

            # Remove the container
            try:
                container.remove(force=force)
                logger.info(f"Removed container: {container_name} ({container_id})")

                return dockyard_pb2.RemoveContainerResponse(
                    success=True,
                    container_id=container_id,
                    message=f"Container '{container_name}' removed successfully"
                )

            except docker.errors.APIError as e:
                return dockyard_pb2.RemoveContainerResponse(
                    success=False,
                    message=f"Failed to remove container: {str(e)}"
                )

        except Exception as e:
            logger.error(f"RemoveContainer error: {e}")
            return dockyard_pb2.RemoveContainerResponse(
                success=False,
                message=f"Error removing container: {str(e)}"
            )

    def GetStats(self, request, context):
        """Stream container statistics"""
        import time
        from datetime import datetime

        try:
            container_identifiers = list(request.container_identifiers)
            stream = request.stream

            # If no specific containers requested, get all running containers
            if not container_identifiers:
                containers = self.docker_client.containers.list(filters={'status': 'running'})
            else:
                containers = []
                for identifier in container_identifiers:
                    try:
                        container = self.docker_client.containers.get(identifier)
                        container.reload()
                        if container.status == 'running':
                            containers.append(container)
                        else:
                            logger.warning(f"Container {identifier} is not running")
                    except docker.errors.NotFound:
                        logger.warning(f"Container {identifier} not found")
                        continue

            if not containers:
                yield dockyard_pb2.StatsResponse(
                    success=False,
                    message="No running containers found"
                )
                return

            logger.info(f"Getting stats for {len(containers)} containers, stream={stream}")

            while True:
                try:
                    stats_list = []
                    timestamp = datetime.utcnow().isoformat() + 'Z'

                    for container in containers:
                        try:
                            # Get stats (non-streaming to avoid blocking)
                            stats = container.stats(stream=False)

                            # Calculate CPU percentage
                            cpu_delta = stats['cpu_stats']['cpu_usage']['total_usage'] - \
                                       stats['precpu_stats']['cpu_usage']['total_usage']
                            system_delta = stats['cpu_stats']['system_cpu_usage'] - \
                                          stats['precpu_stats']['system_cpu_usage']

                            cpu_percentage = 0.0
                            if system_delta > 0:
                                # Get number of CPUs safely
                                percpu_usage = stats['cpu_stats']['cpu_usage'].get('percpu_usage', [])
                                num_cpus = len(percpu_usage) if percpu_usage else 1
                                cpu_percentage = (cpu_delta / system_delta) * num_cpus * 100.0

                            # Memory stats
                            memory_usage = stats['memory_stats'].get('usage', 0)
                            memory_limit = stats['memory_stats'].get('limit', 0)
                            memory_percentage = 0.0
                            if memory_limit > 0:
                                memory_percentage = (memory_usage / memory_limit) * 100.0

                            # Network stats
                            network_rx = 0
                            network_tx = 0
                            if 'networks' in stats:
                                for interface in stats['networks'].values():
                                    network_rx += interface.get('rx_bytes', 0)
                                    network_tx += interface.get('tx_bytes', 0)

                            # Block I/O stats
                            block_read = 0
                            block_write = 0
                            if 'blkio_stats' in stats and 'io_service_bytes_recursive' in stats['blkio_stats']:
                                for entry in stats['blkio_stats']['io_service_bytes_recursive']:
                                    if entry['op'] == 'Read':
                                        block_read += entry['value']
                                    elif entry['op'] == 'Write':
                                        block_write += entry['value']

                            # PIDs
                            pids = stats.get('pids_stats', {}).get('current', 0)

                            container_stats = dockyard_pb2.ContainerStats(
                                container_id=container.id[:12],
                                name=container.name,
                                cpu_percentage=round(cpu_percentage, 2),
                                memory_usage=memory_usage,
                                memory_limit=memory_limit,
                                memory_percentage=round(memory_percentage, 2),
                                network_rx=network_rx,
                                network_tx=network_tx,
                                block_read=block_read,
                                block_write=block_write,
                                pids=pids
                            )

                            stats_list.append(container_stats)

                        except Exception as e:
                            logger.warning(f"Error getting stats for container {container.name}: {e}")
                            continue

                    # Yield the stats
                    yield dockyard_pb2.StatsResponse(
                        stats=stats_list,
                        timestamp=timestamp,
                        message=f"Stats for {len(stats_list)} containers",
                        success=True
                    )

                    # If not streaming, break after first collection
                    if not stream:
                        break

                    # Wait 1 second before next collection
                    time.sleep(1)

                except Exception as e:
                    logger.error(f"Error in stats collection: {e}")
                    yield dockyard_pb2.StatsResponse(
                        success=False,
                        message=f"Error collecting stats: {str(e)}"
                    )
                    break

        except Exception as e:
            logger.error(f"GetStats error: {e}")
            yield dockyard_pb2.StatsResponse(
                success=False,
                message=f"Internal error: {str(e)}"
            )


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