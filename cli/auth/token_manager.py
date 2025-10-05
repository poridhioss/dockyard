"""
Token management for Dockyard CLI
"""
import os
import yaml
from typing import Optional
from cli.utils.exceptions import AuthenticationException


class TokenManager:
    """Manages authentication tokens for CLI"""

    def __init__(self, config_path: Optional[str] = None):
        """Initialize token manager

        Args:
            config_path: Path to config file
        """
        self.config_path = config_path or os.path.expanduser('~/.dockyard/config.yaml')
        self.token: Optional[str] = None
        self.load_token()

    def load_token(self):
        """Load token from environment variable or config file

        Priority:
        1. Environment variable DOCKYARD_AUTH_TOKEN
        2. Config file
        """
        # Priority 1: Environment variable
        self.token = os.getenv('DOCKYARD_AUTH_TOKEN')

        if self.token:
            return self.token

        # Priority 2: Config file
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r') as f:
                    config = yaml.safe_load(f) or {}
                    self.token = config.get('auth', {}).get('token')
            except Exception as e:
                pass

        return self.token

    def get_token(self) -> str:
        """Get authentication token

        Returns:
            Authentication token

        Raises:
            AuthenticationException: If no token is found
        """
        if not self.token:
            raise AuthenticationException(
                "No authentication token found. "
                "Set DOCKYARD_AUTH_TOKEN environment variable or configure in ~/.dockyard/config.yaml"
            )
        return self.token

    def save_token(self, token: str):
        """Save token to config file

        Args:
            token: Authentication token
        """
        # Ensure directory exists
        os.makedirs(os.path.dirname(self.config_path), exist_ok=True)

        # Load existing config
        config = {}
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r') as f:
                    config = yaml.safe_load(f) or {}
            except Exception:
                pass

        # Update auth section
        if 'auth' not in config:
            config['auth'] = {}
        config['auth']['token'] = token

        # Write to file
        with open(self.config_path, 'w') as f:
            yaml.dump(config, f, default_flow_style=False)

        # Set restrictive permissions
        try:
            os.chmod(self.config_path, 0o600)
        except Exception:
            pass  # Windows doesn't support chmod

        self.token = token

    def has_token(self) -> bool:
        """Check if token is available

        Returns:
            True if token is available
        """
        return self.token is not None
