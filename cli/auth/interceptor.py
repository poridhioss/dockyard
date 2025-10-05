"""
gRPC client authentication interceptor for Dockyard CLI
"""
import grpc


class TokenAuthClientInterceptor(
    grpc.UnaryUnaryClientInterceptor,
    grpc.UnaryStreamClientInterceptor,
    grpc.StreamUnaryClientInterceptor,
    grpc.StreamStreamClientInterceptor
):
    """gRPC client interceptor for token authentication"""

    def __init__(self, token_manager):
        """Initialize interceptor

        Args:
            token_manager: TokenManager instance
        """
        self.token_manager = token_manager

    def _add_auth_metadata(self, client_call_details):
        """Add authentication token to request metadata

        Args:
            client_call_details: Client call details

        Returns:
            Modified client call details with auth metadata
        """
        metadata = []
        if client_call_details.metadata:
            metadata = list(client_call_details.metadata)

        # Add authorization token if available
        if self.token_manager.has_token():
            token = self.token_manager.get_token()
            metadata.append(('authorization', token))

        return client_call_details._replace(metadata=metadata)

    def intercept_unary_unary(self, continuation, client_call_details, request):
        """Intercept unary-unary calls"""
        new_details = self._add_auth_metadata(client_call_details)
        return continuation(new_details, request)

    def intercept_unary_stream(self, continuation, client_call_details, request):
        """Intercept unary-stream calls"""
        new_details = self._add_auth_metadata(client_call_details)
        return continuation(new_details, request)

    def intercept_stream_unary(self, continuation, client_call_details, request_iterator):
        """Intercept stream-unary calls"""
        new_details = self._add_auth_metadata(client_call_details)
        return continuation(new_details, request_iterator)

    def intercept_stream_stream(self, continuation, client_call_details, request_iterator):
        """Intercept stream-stream calls"""
        new_details = self._add_auth_metadata(client_call_details)
        return continuation(new_details, request_iterator)
