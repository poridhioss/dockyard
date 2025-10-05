"""
Logs service for Dockyard Agent
Handles container logs operations with streaming support
"""
from typing import Iterator
from datetime import datetime, timedelta
from agent.utils.logger import get_logger
from agent.utils.exceptions import ContainerNotFoundException

logger = get_logger(__name__)


class LogsService:
    """Service for container logs operations"""

    def __init__(self, docker_client):
        """Initialize logs service

        Args:
            docker_client: DockerClientWrapper instance
        """
        self.docker_client = docker_client.client

    def get_logs(
        self,
        container_identifier: str,
        follow: bool = False,
        tail: int = None,
        since: str = None,
        timestamps: bool = False,
        stdout: bool = True,
        stderr: bool = True
    ) -> Iterator[bytes]:
        """Get container logs with streaming support

        Args:
            container_identifier: Container name or ID
            follow: Follow log output (stream mode)
            tail: Number of lines from the end (all if None)
            since: Show logs since timestamp or duration (e.g., "1h", "2023-01-01")
            timestamps: Include timestamps
            stdout: Include stdout
            stderr: Include stderr

        Yields:
            Log data chunks
        """
        try:
            container = self.docker_client.containers.get(container_identifier)
            logger.info(f"Getting logs for container {container_identifier}")

            # Parse 'since' parameter
            since_time = self._parse_since(since) if since else None

            # Get logs
            log_stream = container.logs(
                stdout=stdout,
                stderr=stderr,
                stream=follow,
                follow=follow,
                timestamps=timestamps,
                tail=tail if tail else 'all',
                since=since_time
            )

            # Stream logs
            if follow:
                # Streaming mode
                for log_line in log_stream:
                    yield log_line
            else:
                # Non-streaming mode
                yield log_stream

            logger.info(f"Logs streaming completed for {container_identifier}")

        except Exception as e:
            logger.error(f"Failed to get logs for {container_identifier}: {e}")
            error_msg = f"Error: {str(e)}\n".encode()
            yield error_msg

    def _parse_since(self, since: str):
        """Parse 'since' parameter to datetime or relative time

        Args:
            since: Time string (e.g., "1h", "30m", "2023-01-01T12:00:00")

        Returns:
            Parsed datetime or relative time
        """
        try:
            # Try parsing as duration (e.g., "1h", "30m", "2d")
            if since.endswith('s'):
                seconds = int(since[:-1])
                return datetime.utcnow() - timedelta(seconds=seconds)
            elif since.endswith('m'):
                minutes = int(since[:-1])
                return datetime.utcnow() - timedelta(minutes=minutes)
            elif since.endswith('h'):
                hours = int(since[:-1])
                return datetime.utcnow() - timedelta(hours=hours)
            elif since.endswith('d'):
                days = int(since[:-1])
                return datetime.utcnow() - timedelta(days=days)
            else:
                # Try parsing as ISO timestamp
                return datetime.fromisoformat(since.replace('Z', '+00:00'))
        except Exception as e:
            logger.warning(f"Failed to parse 'since' parameter '{since}': {e}")
            return None
