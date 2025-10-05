"""
Stats service for Dockyard Agent
Handles container resource statistics monitoring
"""
import time
from typing import Iterator, List
from datetime import datetime
from agent.utils.logger import get_logger
from agent.utils.exceptions import ContainerNotFoundException

logger = get_logger(__name__)


class StatsService:
    """Service for container statistics operations"""

    def __init__(self, docker_client):
        """Initialize stats service

        Args:
            docker_client: DockerClientWrapper instance
        """
        self.docker_client = docker_client.client

    def get_stats(
        self,
        container_identifiers: List[str] = None,
        stream: bool = True
    ) -> Iterator[dict]:
        """Get container resource statistics

        Args:
            container_identifiers: List of container names/IDs (None = all running)
            stream: Stream continuous updates

        Yields:
            Dictionary with container statistics
        """
        try:
            # Get containers to monitor
            if container_identifiers:
                containers = []
                for identifier in container_identifiers:
                    try:
                        container = self.docker_client.containers.get(identifier)
                        containers.append(container)
                    except Exception as e:
                        logger.warning(f"Container {identifier} not found: {e}")
            else:
                containers = self.docker_client.containers.list()

            if not containers:
                logger.warning("No running containers found")
                yield {
                    'timestamp': datetime.utcnow().isoformat() + 'Z',
                    'containers': []
                }
                return

            logger.info(f"Getting stats for {len(containers)} containers, stream={stream}")

            # Stream statistics
            while True:
                stats_list = []
                timestamp = datetime.utcnow().isoformat() + 'Z'

                for container in containers:
                    try:
                        # Get stats (non-streaming to avoid blocking)
                        stats = container.stats(stream=False)

                        # Calculate CPU percentage
                        cpu_percentage = self._calculate_cpu_percentage(stats)

                        # Memory stats
                        memory_usage = stats['memory_stats'].get('usage', 0)
                        memory_limit = stats['memory_stats'].get('limit', 0)
                        memory_percentage = (memory_usage / memory_limit * 100) if memory_limit > 0 else 0.0

                        # Network stats
                        network_rx, network_tx = self._calculate_network_io(stats)

                        # Block I/O stats
                        block_read, block_write = self._calculate_block_io(stats)

                        # PIDs
                        pids = stats.get('pids_stats', {}).get('current', 0)

                        container_stats = {
                            'container_id': container.short_id,
                            'name': container.name,
                            'cpu_percentage': cpu_percentage,
                            'memory_usage': memory_usage,
                            'memory_limit': memory_limit,
                            'memory_percentage': memory_percentage,
                            'network_rx': network_rx,
                            'network_tx': network_tx,
                            'block_read': block_read,
                            'block_write': block_write,
                            'pids': pids
                        }
                        stats_list.append(container_stats)

                    except Exception as e:
                        logger.warning(f"Error getting stats for container {container.name}: {e}")
                        continue

                # Yield stats
                yield {
                    'timestamp': timestamp,
                    'containers': stats_list
                }

                # Break if not streaming
                if not stream:
                    break

                # Wait before next update
                time.sleep(1)

        except Exception as e:
            logger.error(f"Failed to get stats: {e}")
            yield {
                'timestamp': datetime.utcnow().isoformat() + 'Z',
                'containers': [],
                'error': str(e)
            }

    def _calculate_cpu_percentage(self, stats: dict) -> float:
        """Calculate CPU percentage from stats

        Args:
            stats: Container stats dictionary

        Returns:
            CPU percentage
        """
        try:
            cpu_delta = stats['cpu_stats']['cpu_usage']['total_usage'] - \
                       stats['precpu_stats']['cpu_usage']['total_usage']
            system_delta = stats['cpu_stats']['system_cpu_usage'] - \
                          stats['precpu_stats']['system_cpu_usage']

            if system_delta > 0:
                # Get number of CPUs safely
                percpu_usage = stats['cpu_stats']['cpu_usage'].get('percpu_usage', [])
                num_cpus = len(percpu_usage) if percpu_usage else 1
                cpu_percentage = (cpu_delta / system_delta) * num_cpus * 100.0
                return round(cpu_percentage, 2)

            return 0.0

        except Exception as e:
            logger.debug(f"Error calculating CPU percentage: {e}")
            return 0.0

    def _calculate_network_io(self, stats: dict) -> tuple:
        """Calculate network I/O from stats

        Args:
            stats: Container stats dictionary

        Returns:
            Tuple of (rx_bytes, tx_bytes)
        """
        try:
            networks = stats.get('networks', {})
            rx_bytes = 0
            tx_bytes = 0

            for interface, data in networks.items():
                rx_bytes += data.get('rx_bytes', 0)
                tx_bytes += data.get('tx_bytes', 0)

            return rx_bytes, tx_bytes

        except Exception as e:
            logger.debug(f"Error calculating network I/O: {e}")
            return 0, 0

    def _calculate_block_io(self, stats: dict) -> tuple:
        """Calculate block I/O from stats

        Args:
            stats: Container stats dictionary

        Returns:
            Tuple of (read_bytes, write_bytes)
        """
        try:
            blkio_stats = stats.get('blkio_stats', {})
            io_service_bytes = blkio_stats.get('io_service_bytes_recursive', [])

            read_bytes = 0
            write_bytes = 0

            for entry in io_service_bytes:
                if entry.get('op') == 'Read':
                    read_bytes += entry.get('value', 0)
                elif entry.get('op') == 'Write':
                    write_bytes += entry.get('value', 0)

            return read_bytes, write_bytes

        except Exception as e:
            logger.debug(f"Error calculating block I/O: {e}")
            return 0, 0
