"""
Configuration management for Dockyard CLI
"""
import os
import yaml
from typing import Optional


class CLIConfig:
    """CLI configuration management"""

    def __init__(self, config_path: Optional[str] = None):
        """Initialize configuration

        Args:
            config_path: Path to config file (default: ~/.dockyard/config.yaml)
        """
        self.config_path = config_path or os.path.expanduser('~/.dockyard/config.yaml')
        self.config = self._load_config()

    def _load_config(self) -> dict:
        """Load configuration from file"""
        default_config = {
            'default_host': 'localhost',
            'default_port': 50051,
            'timeout': 60,
            'output_format': 'table',
            'auth': {}
        }

        # Try to load from file
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r') as f:
                    file_config = yaml.safe_load(f) or {}
                    # Merge with defaults
                    return {**default_config, **file_config}
            except Exception as e:
                print(f"Warning: Failed to load config file: {e}")
                return default_config

        return default_config

    @property
    def default_host(self) -> str:
        """Get default host"""
        return os.getenv('DOCKYARD_HOST', self.config['default_host'])

    @property
    def default_port(self) -> int:
        """Get default port"""
        return int(os.getenv('DOCKYARD_PORT', self.config['default_port']))

    @property
    def timeout(self) -> int:
        """Get timeout"""
        return self.config['timeout']

    @property
    def output_format(self) -> str:
        """Get output format"""
        return self.config['output_format']

    @property
    def auth_token(self) -> Optional[str]:
        """Get authentication token

        Priority:
        1. Environment variable
        2. Config file
        """
        # Priority 1: Environment variable
        token = os.getenv('DOCKYARD_AUTH_TOKEN')
        if token:
            return token

        # Priority 2: Config file
        return self.config.get('auth', {}).get('token')

    def save_config(self, updates: dict):
        """Save configuration updates to file

        Args:
            updates: Dictionary of configuration updates
        """
        # Merge updates with existing config
        self.config.update(updates)

        # Ensure directory exists
        os.makedirs(os.path.dirname(self.config_path), exist_ok=True)

        # Write to file
        with open(self.config_path, 'w') as f:
            yaml.dump(self.config, f, default_flow_style=False)

        # Set restrictive permissions
        os.chmod(self.config_path, 0o600)

    def save_token(self, token: str):
        """Save authentication token to config file

        Args:
            token: Authentication token
        """
        if 'auth' not in self.config:
            self.config['auth'] = {}

        self.config['auth']['token'] = token
        self.save_config(self.config)
