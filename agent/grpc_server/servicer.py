"""
gRPC servicer implementation for Dockyard Agent
"""
import sys
import os

# Add parent directory to path for proto imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import dockyard_pb2
import dockyard_pb2_grpc

from agent.utils.logger import get_logger
from agent.services.container_service import ContainerService
from agent.services.exec_service import ExecService
from agent.services.logs_service import LogsService
from agent.services.stats_service import StatsService

logger = get_logger(__name__)


class DockyardServicer(dockyard_pb2_grpc.DockyardServiceServicer):
    """gRPC servicer for Dockyard operations"""

    def __init__(self, docker_client):
        """Initialize servicer with Docker client

        Args:
            docker_client: DockerClientWrapper instance
        """
        self.docker_client = docker_client

        # Initialize services
        self.container_service = ContainerService(docker_client)
        self.exec_service = ExecService(docker_client)
        self.logs_service = LogsService(docker_client)
        self.stats_service = StatsService(docker_client)

        logger.info("DockyardServicer initialized")

    def LaunchContainer(self, request, context):
        """Launch a new container

        Args:
            request: LaunchRequest
            context: gRPC context

        Returns:
            LaunchResponse
        """
        try:
            success, message, container_id = self.container_service.launch_container(
                image=request.image,
                name=request.name if request.name else None,
                config_file=request.config_file if request.config_file else None
            )

            return dockyard_pb2.LaunchResponse(
                success=success,
                message=message,
                container_id=container_id or ''
            )

        except Exception as e:
            logger.error(f"LaunchContainer failed: {e}")
            return dockyard_pb2.LaunchResponse(
                success=False,
                message=f"Failed to launch container: {str(e)}",
                container_id=''
            )

    def StopContainer(self, request, context):
        """Stop a container

        Args:
            request: StopRequest
            context: gRPC context

        Returns:
            StopResponse
        """
        try:
            success, message = self.container_service.stop_container(
                container_identifier=request.container_identifier,
                force=request.force,
                timeout=request.timeout if request.timeout > 0 else 10
            )

            return dockyard_pb2.StopResponse(
                success=success,
                message=message
            )

        except Exception as e:
            logger.error(f"StopContainer failed: {e}")
            return dockyard_pb2.StopResponse(
                success=False,
                message=f"Failed to stop container: {str(e)}"
            )

    def ExecContainer(self, request_iterator, context):
        """Execute command in container with bidirectional streaming

        Args:
            request_iterator: Iterator of ExecRequest
            context: gRPC context

        Yields:
            ExecResponse
        """
        try:
            # Get first request with exec configuration
            first_request = next(request_iterator)

            if not first_request.HasField('start'):
                yield dockyard_pb2.ExecResponse(
                    status=dockyard_pb2.ExecStatus(
                        success=False,
                        message="First request must contain exec start configuration",
                        finished=True
                    )
                )
                return

            start_config = first_request.start

            # Create input iterator for remaining requests
            def input_generator():
                try:
                    for req in request_iterator:
                        if req.HasField('input'):
                            yield req.input.data
                except Exception as e:
                    logger.error(f"Input iterator error: {e}")

            # Execute command
            for output in self.exec_service.execute_command(
                container_identifier=start_config.container_identifier,
                command=list(start_config.command),
                interactive=start_config.interactive,
                user=start_config.user if start_config.user else None,
                working_dir=start_config.working_dir if start_config.working_dir else None,
                environment=dict(start_config.environment) if start_config.environment else None,
                input_iterator=input_generator() if start_config.interactive else None
            ):
                if output['exit_code'] is not None:
                    # Send exit code
                    yield dockyard_pb2.ExecResponse(
                        status=dockyard_pb2.ExecStatus(
                            success=True,
                            exit_code=output['exit_code'],
                            message="Command completed",
                            finished=True
                        )
                    )
                else:
                    # Send output
                    yield dockyard_pb2.ExecResponse(
                        output=dockyard_pb2.ExecOutput(
                            data=output['stdout'] or output['stderr'],
                            stream_type="stdout" if output['stdout'] else "stderr"
                        )
                    )

        except Exception as e:
            logger.error(f"ExecContainer failed: {e}")
            yield dockyard_pb2.ExecResponse(
                status=dockyard_pb2.ExecStatus(
                    success=False,
                    message=f"Exec failed: {str(e)}",
                    finished=True
                )
            )

    def GetLogs(self, request, context):
        """Get container logs with streaming

        Args:
            request: LogsRequest
            context: gRPC context

        Yields:
            LogsResponse
        """
        try:
            for log_data in self.logs_service.get_logs(
                container_identifier=request.container_identifier,
                follow=request.follow,
                tail=request.tail if request.tail > 0 else None,
                since=request.since if request.since else None,
                timestamps=request.timestamps,
                stdout=request.stdout,
                stderr=request.stderr
            ):
                yield dockyard_pb2.LogsResponse(
                    log=dockyard_pb2.LogEntry(
                        data=log_data,
                        stream_type="stdout"
                    )
                )

            # Send finished status for non-follow mode
            if not request.follow:
                yield dockyard_pb2.LogsResponse(
                    status=dockyard_pb2.LogsStatus(
                        success=True,
                        message="Logs completed",
                        finished=True
                    )
                )

        except Exception as e:
            logger.error(f"GetLogs failed: {e}")
            yield dockyard_pb2.LogsResponse(
                status=dockyard_pb2.LogsStatus(
                    success=False,
                    message=f"Error: {str(e)}",
                    finished=True
                )
            )

    def ListContainers(self, request, context):
        """List containers

        Args:
            request: ListContainersRequest
            context: gRPC context

        Returns:
            ListContainersResponse
        """
        try:
            containers = self.container_service.list_containers(all=request.all)

            container_infos = []
            for container in containers:
                container_infos.append(dockyard_pb2.ContainerInfo(
                    id=container['id'],
                    image=container['image'],
                    command=container['command'],
                    created=container['created'],
                    status=container['status'],
                    ports=container['ports'],
                    names=container['names']
                ))

            return dockyard_pb2.ListContainersResponse(
                success=True,
                containers=container_infos,
                message=f"Found {len(containers)} containers"
            )

        except Exception as e:
            logger.error(f"ListContainers failed: {e}")
            return dockyard_pb2.ListContainersResponse(
                success=False,
                containers=[],
                message=f"Failed to list containers: {str(e)}"
            )

    def InspectContainer(self, request, context):
        """Inspect container

        Args:
            request: InspectContainerRequest
            context: gRPC context

        Returns:
            InspectContainerResponse
        """
        try:
            json_data = self.container_service.inspect_container(
                container_identifier=request.container_identifier
            )

            return dockyard_pb2.InspectContainerResponse(
                success=True,
                json_data=json_data,
                message=f"Container '{request.container_identifier}' inspected successfully"
            )

        except Exception as e:
            logger.error(f"InspectContainer failed: {e}")
            return dockyard_pb2.InspectContainerResponse(
                success=False,
                json_data='',
                message=f"Failed to inspect container: {str(e)}"
            )

    def RemoveContainer(self, request, context):
        """Remove container

        Args:
            request: RemoveContainerRequest
            context: gRPC context

        Returns:
            RemoveContainerResponse
        """
        try:
            success, message, container_id = self.container_service.remove_container(
                container_identifier=request.container_identifier,
                force=request.force,
                volumes=False
            )

            return dockyard_pb2.RemoveContainerResponse(
                success=success,
                message=message,
                container_id=container_id or ''
            )

        except Exception as e:
            logger.error(f"RemoveContainer failed: {e}")
            return dockyard_pb2.RemoveContainerResponse(
                success=False,
                message=f"Failed to remove container: {str(e)}",
                container_id=''
            )

    def GetStats(self, request, context):
        """Get container statistics with streaming

        Args:
            request: StatsRequest
            context: gRPC context

        Yields:
            StatsResponse
        """
        try:
            container_ids = list(request.container_identifiers) if request.container_identifiers else None

            for stats_data in self.stats_service.get_stats(
                container_identifiers=container_ids,
                stream=request.stream
            ):
                container_stats = []
                for container in stats_data.get('containers', []):
                    container_stats.append(dockyard_pb2.ContainerStats(
                        container_id=container['container_id'],
                        name=container['name'],
                        cpu_percentage=container['cpu_percentage'],
                        memory_usage=container['memory_usage'],
                        memory_limit=container['memory_limit'],
                        memory_percentage=container['memory_percentage'],
                        network_rx=container['network_rx'],
                        network_tx=container['network_tx'],
                        block_read=container['block_read'],
                        block_write=container['block_write'],
                        pids=container['pids']
                    ))

                yield dockyard_pb2.StatsResponse(
                    success=True,
                    stats=container_stats,
                    timestamp=stats_data.get('timestamp', ''),
                    message=''
                )

        except Exception as e:
            logger.error(f"GetStats failed: {e}")
            yield dockyard_pb2.StatsResponse(
                success=False,
                stats=[],
                timestamp='',
                message=f"Failed to get stats: {str(e)}"
            )
