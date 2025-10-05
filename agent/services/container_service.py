"""
Container service for Dockyard Agent
Handles all container lifecycle operations
"""
import json
import yaml
from pathlib import Path
from typing import List, Dict, Any
from agent.utils.logger import get_logger
from agent.utils.exceptions import (
    ContainerNotFoundException,
    ContainerOperationException,
    ImageNotFoundException
)
from agent.docker_client.utils import format_ports, format_timestamp, truncate_string

logger = get_logger(__name__)


class ContainerService:
    """Service for container operations"""

    def __init__(self, docker_client):
        """Initialize container service

        Args:
            docker_client: DockerClientWrapper instance
        """
        self.docker_client = docker_client.client

    def launch_container(
        self,
        image: str,
        name: str = None,
        config_file: str = None,
        **kwargs
    ) -> tuple:
        """Launch a new container

        Args:
            image: Docker image name
            name: Container name (optional)
            config_file: Path to YAML config file (optional)
            **kwargs: Additional container configuration

        Returns:
            Tuple of (success, message, container_id)
        """
        try:
            container_config = {}

            # Load from config file if provided
            if config_file:
                config_path = Path(config_file)
                if config_path.exists():
                    with open(config_path, 'r') as f:
                        config = yaml.safe_load(f)
                        container_config = self._parse_config(config)
                else:
                    return False, f"Config file not found: {config_file}", None

            # Basic configuration
            if not container_config:
                container_config = {
                    'image': image,
                    'detach': True
                }
                if name:
                    container_config['name'] = name

            # Merge with kwargs
            container_config.update(kwargs)

            # Ensure image exists
            try:
                self.docker_client.images.get(image)
                logger.info(f"Image {image} already exists")
            except:
                logger.info(f"Pulling image {image}...")
                self.docker_client.images.pull(image)
                logger.info(f"Image {image} pulled successfully")

            # Create and start container
            container = self.docker_client.containers.run(**container_config)
            container_id = container.short_id
            container_name = name or container.name

            logger.info(f"Container launched: {container_name} ({container_id})")
            return True, f"Container '{container_name}' launched successfully", container_id

        except Exception as e:
            logger.error(f"Failed to launch container: {e}")
            return False, f"Failed to launch container: {str(e)}", None

    def stop_container(
        self,
        container_identifier: str,
        force: bool = False,
        timeout: int = 10
    ) -> tuple:
        """Stop a container

        Args:
            container_identifier: Container name or ID
            force: Force kill the container
            timeout: Timeout for graceful stop

        Returns:
            Tuple of (success, message)
        """
        try:
            container = self.docker_client.containers.get(container_identifier)

            if force:
                container.kill()
                logger.info(f"Container {container_identifier} killed")
                message = f"Container '{container_identifier}' killed"
            else:
                container.stop(timeout=timeout)
                logger.info(f"Container {container_identifier} stopped")
                message = f"Container '{container_identifier}' stopped"

            return True, message

        except Exception as e:
            logger.error(f"Failed to stop container {container_identifier}: {e}")
            return False, f"Failed to stop container: {str(e)}"

    def list_containers(self, all: bool = False) -> List[Dict[str, str]]:
        """List containers

        Args:
            all: List all containers (including stopped)

        Returns:
            List of container info dictionaries
        """
        try:
            containers = self.docker_client.containers.list(all=all)
            container_list = []

            for container in containers:
                # Format creation time
                created_time = container.attrs['Created'][:19].replace('T', ' ')

                # Extract port information
                port_info = format_ports(container.ports)

                # Get image name
                image = container.image.tags[0] if container.image.tags else container.image.id[:12]

                # Get command
                cmd = container.attrs['Config']['Cmd'] or []
                command = ' '.join(cmd) if cmd else ''

                container_info = {
                    'id': container.short_id,
                    'image': image,
                    'command': truncate_string(command, 30),
                    'created': created_time,
                    'status': container.status,
                    'ports': port_info,
                    'names': container.name
                }
                container_list.append(container_info)

            logger.info(f"Listed {len(container_list)} containers (all={all})")
            return container_list

        except Exception as e:
            logger.error(f"Failed to list containers: {e}")
            raise ContainerOperationException(f"Failed to list containers: {e}")

    def inspect_container(self, container_identifier: str) -> str:
        """Inspect container details

        Args:
            container_identifier: Container name or ID

        Returns:
            JSON string of container inspection data
        """
        try:
            container = self.docker_client.containers.get(container_identifier)
            inspection_data = container.attrs

            logger.info(f"Inspected container: {container_identifier}")
            return json.dumps(inspection_data, indent=2)

        except Exception as e:
            logger.error(f"Failed to inspect container {container_identifier}: {e}")
            raise ContainerNotFoundException(f"Container not found: {container_identifier}")

    def remove_container(
        self,
        container_identifier: str,
        force: bool = False,
        volumes: bool = False
    ) -> tuple:
        """Remove a container

        Args:
            container_identifier: Container name or ID
            force: Force remove running container
            volumes: Remove associated volumes

        Returns:
            Tuple of (success, message, container_id)
        """
        try:
            container = self.docker_client.containers.get(container_identifier)
            container_id = container.short_id

            # Check if container is running
            if container.status == 'running' and not force:
                return False, f"Container '{container_identifier}' is running. Use --force to remove.", None

            container.remove(force=force, v=volumes)
            logger.info(f"Removed container: {container_identifier} ({container_id})")
            return True, f"Container '{container_identifier}' removed successfully", container_id

        except Exception as e:
            logger.error(f"Failed to remove container {container_identifier}: {e}")
            return False, f"Failed to remove container: {str(e)}", None

    def _parse_config(self, config: dict) -> dict:
        """Parse YAML configuration to Docker container config

        Args:
            config: Configuration dictionary from YAML

        Returns:
            Docker container configuration dict
        """
        container_config = {
            'image': config.get('image'),
            'detach': True
        }

        if 'name' in config:
            container_config['name'] = config['name']

        if 'command' in config:
            container_config['command'] = config['command']

        if 'environment' in config:
            container_config['environment'] = config['environment']

        if 'ports' in config:
            container_config['ports'] = config['ports']

        if 'volumes' in config:
            container_config['volumes'] = config['volumes']

        return container_config
