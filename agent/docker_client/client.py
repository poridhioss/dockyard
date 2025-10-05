"""
Docker client wrapper for Dockyard Agent
"""
import docker
from typing import Optional
from agent.utils.exceptions import DockerClientException
from agent.utils.logger import get_logger

logger = get_logger(__name__)


class DockerClientWrapper:
    """Wrapper around Docker SDK client"""

    def __init__(self, socket: str = 'unix://var/run/docker.sock', timeout: int = 30):
        """Initialize Docker client

        Args:
            socket: Docker socket path
            timeout: Connection timeout in seconds
        """
        self.socket = socket
        self.timeout = timeout
        self._client: Optional[docker.DockerClient] = None
        self._connect()

    def _connect(self):
        """Establish connection to Docker daemon"""
        try:
            self._client = docker.DockerClient(
                base_url=self.socket,
                timeout=self.timeout
            )
            # Test connection
            self._client.ping()
            logger.info(f"Connected to Docker daemon at {self.socket}")
        except Exception as e:
            logger.error(f"Failed to connect to Docker daemon: {e}")
            raise DockerClientException(f"Failed to connect to Docker: {e}")

    @property
    def client(self) -> docker.DockerClient:
        """Get Docker client instance

        Returns:
            Docker client instance
        """
        if not self._client:
            self._connect()
        return self._client

    def ping(self) -> bool:
        """Ping Docker daemon

        Returns:
            True if connection is alive
        """
        try:
            return self.client.ping()
        except Exception as e:
            logger.warning(f"Docker ping failed: {e}")
            return False

    def close(self):
        """Close Docker client connection"""
        if self._client:
            try:
                self._client.close()
                logger.info("Docker client connection closed")
            except Exception as e:
                logger.warning(f"Error closing Docker client: {e}")
            finally:
                self._client = None

    def __enter__(self):
        """Context manager entry"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.close()
