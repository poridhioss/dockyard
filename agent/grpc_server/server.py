"""
gRPC server setup for Dockyard Agent
"""
import sys
import os
import grpc
from concurrent import futures

# Add parent directory to path for proto imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import dockyard_pb2_grpc

from agent.utils.logger import get_logger
from agent.grpc_server.servicer import DockyardServicer
from agent.auth.interceptor import TokenAuthInterceptor
from agent.auth.token_validator import TokenValidator

logger = get_logger(__name__)


class DockyardServer:
    """gRPC server for Dockyard Agent"""

    def __init__(self, docker_client, config):
        """Initialize server

        Args:
            docker_client: DockerClientWrapper instance
            config: AgentConfig instance
        """
        self.docker_client = docker_client
        self.config = config
        self.server = None

    def start(self):
        """Start the gRPC server"""
        try:
            # Create servicer
            servicer = DockyardServicer(self.docker_client)

            # Create server
            self.server = grpc.server(
                futures.ThreadPoolExecutor(max_workers=self.config.max_workers)
            )

            # Add authentication interceptor if enabled
            if self.config.auth_enabled:
                validator = TokenValidator()
                if validator.is_enabled:
                    interceptor = TokenAuthInterceptor(validator)
                    self.server = grpc.server(
                        futures.ThreadPoolExecutor(max_workers=self.config.max_workers),
                        interceptors=(interceptor,)
                    )
                    logger.info("Authentication enabled")
                else:
                    logger.warning("Authentication configured but no token set - running without auth")

            # Add servicer to server
            dockyard_pb2_grpc.add_DockyardServiceServicer_to_server(servicer, self.server)

            # Bind to address
            address = f'{self.config.server_host}:{self.config.server_port}'
            self.server.add_insecure_port(address)

            # Start server
            self.server.start()
            logger.info(f"Agent started on {address}")

            return self.server

        except Exception as e:
            logger.error(f"Failed to start server: {e}")
            raise

    def stop(self, grace_period=10):
        """Stop the gRPC server

        Args:
            grace_period: Grace period in seconds for shutdown
        """
        if self.server:
            logger.info(f"Stopping server (grace period: {grace_period}s)...")
            self.server.stop(grace_period)
            logger.info("Server stopped")

    def wait_for_termination(self):
        """Wait for server termination"""
        if self.server:
            try:
                self.server.wait_for_termination()
            except KeyboardInterrupt:
                logger.info("Received interrupt signal")
                self.stop()
