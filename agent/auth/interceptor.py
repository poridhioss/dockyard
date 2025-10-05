"""
gRPC authentication interceptor for Dockyard Agent
"""
import grpc
from agent.utils.logger import get_logger

logger = get_logger(__name__)


class TokenAuthInterceptor(grpc.ServerInterceptor):
    """gRPC server interceptor for token authentication"""

    def __init__(self, validator):
        """Initialize interceptor

        Args:
            validator: TokenValidator instance
        """
        self.validator = validator

    def intercept_service(self, continuation, handler_call_details):
        """Intercept all gRPC calls to validate authentication token

        Args:
            continuation: Continuation function
            handler_call_details: Handler call details

        Returns:
            RPC method handler or aborted context
        """
        # Skip authentication if not enabled
        if not self.validator.is_enabled:
            return continuation(handler_call_details)

        # Extract metadata
        metadata = dict(handler_call_details.invocation_metadata)

        # Extract token from authorization header
        auth_token = metadata.get('authorization')

        if not auth_token:
            logger.warning(f"Authentication failed: No token provided for {handler_call_details.method}")
            return self._abort_unauthenticated(
                "Authentication token required. Set DOCKYARD_AUTH_TOKEN."
            )

        # Validate token
        if not self.validator.validate(auth_token):
            logger.warning(f"Authentication failed: Invalid token for {handler_call_details.method}")
            return self._abort_unauthenticated("Invalid authentication token.")

        logger.debug(f"Authentication successful for {handler_call_details.method}")
        return continuation(handler_call_details)

    def _abort_unauthenticated(self, message: str):
        """Abort request with UNAUTHENTICATED status

        Args:
            message: Error message

        Returns:
            Aborted RPC handler
        """
        def abort(request, context):
            context.abort(grpc.StatusCode.UNAUTHENTICATED, message)

        return grpc.unary_unary_rpc_method_handler(
            abort,
            request_deserializer=lambda x: x,
            response_serializer=lambda x: x
        )
