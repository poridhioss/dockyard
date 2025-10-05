"""
Token validation for Dockyard Agent authentication
"""
import os
import secrets
import hashlib
from agent.utils.logger import get_logger
from agent.utils.exceptions import AuthenticationException

logger = get_logger(__name__)


class TokenValidator:
    """Validates authentication tokens"""

    def __init__(self):
        """Initialize validator with token from environment"""
        self.auth_token = os.getenv('DOCKYARD_AUTH_TOKEN')
        if not self.auth_token:
            logger.warning("DOCKYARD_AUTH_TOKEN environment variable not set - authentication disabled")
            self.auth_token = None
        else:
            # Store hash of token for logging (never log actual token)
            self.token_hash = hashlib.sha256(self.auth_token.encode()).hexdigest()[:8]
            logger.info(f"Authentication enabled with token hash: {self.token_hash}")

    def validate(self, provided_token: str) -> bool:
        """Validate provided token against configured token

        Args:
            provided_token: Token to validate

        Returns:
            True if token is valid, False otherwise
        """
        if not self.auth_token:
            # No token configured, allow all (authentication disabled)
            return True

        if not provided_token:
            logger.warning("No token provided in request")
            return False

        # Constant-time comparison to prevent timing attacks
        is_valid = secrets.compare_digest(provided_token, self.auth_token)

        if not is_valid:
            logger.warning("Invalid token provided")
        else:
            logger.debug("Token validated successfully")

        return is_valid

    @property
    def is_enabled(self) -> bool:
        """Check if authentication is enabled

        Returns:
            True if authentication is enabled
        """
        return self.auth_token is not None

    @staticmethod
    def generate_token() -> str:
        """Generate a secure random token

        Returns:
            URL-safe random token string
        """
        return secrets.token_urlsafe(32)
