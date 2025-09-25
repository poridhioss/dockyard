#!/usr/bin/env python3
import sys
import os
import grpc
import docker
import yaml
import logging
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