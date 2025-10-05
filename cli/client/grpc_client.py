"""
gRPC client wrapper for Dockyard CLI
"""
import sys
import os
import grpc

# Add parent directory to path for proto imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import dockyard_pb2
import dockyard_pb2_grpc

from cli.auth.interceptor import TokenAuthClientInterceptor
from cli.auth.token_manager import TokenManager
from cli.utils.exceptions import ConnectionException


class DockyardClient:
    """gRPC client for Dockyard operations"""

    def __init__(self, host: str, port: int, timeout: int = 60):
        """Initialize gRPC client

        Args:
            host: Server hostname
            port: Server port
            timeout: Request timeout in seconds
        """
        self.host = host
        self.port = port
        self.timeout = timeout
        self.address = f"{host}:{port}"

        # Initialize token manager
        self.token_manager = TokenManager()

        # Create channel and stub
        self.channel = None
        self.stub = None
        self._connect()

    def _connect(self):
        """Establish gRPC connection"""
        try:
            # Create channel
            self.channel = grpc.insecure_channel(self.address)

            # Add auth interceptor
            auth_interceptor = TokenAuthClientInterceptor(self.token_manager)
            self.channel = grpc.intercept_channel(self.channel, auth_interceptor)

            # Create stub
            self.stub = dockyard_pb2_grpc.DockyardServiceStub(self.channel)

        except Exception as e:
            raise ConnectionException(f"Failed to connect to {self.address}: {e}")

    def close(self):
        """Close gRPC connection"""
        if self.channel:
            try:
                self.channel.close()
            except Exception:
                pass

    def __enter__(self):
        """Context manager entry"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.close()
