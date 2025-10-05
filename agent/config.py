"""
Configuration management for Dockyard Agent
"""
import os
import yaml
from typing import Optional


class AgentConfig:
    """Agent configuration management"""

    def __init__(self, config_path: Optional[str] = None):
        """Initialize configuration

        Args:
            config_path: Path to config file (default: /etc/dockyard/config.yaml)
        """
        self.config_path = config_path or os.getenv('DOCKYARD_CONFIG', '/etc/dockyard/config.yaml')
        self.config = self._load_config()

    def _load_config(self) -> dict:
        """Load configuration from file"""
        default_config = {
            'server': {
                'host': '0.0.0.0',
                'port': 50051,
                'max_workers': 10
            },
            'docker': {
                'socket': 'unix://var/run/docker.sock',
                'timeout': 30
            },
            'auth': {
                'enabled': True
            },
            'logging': {
                'level': 'INFO',
                'file': '/var/log/dockyard/agent.log',
                'max_size': 10485760,  # 10MB
                'backup_count': 3
            }
        }

        # Try to load from file
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r') as f:
                    file_config = yaml.safe_load(f) or {}
                    # Merge with defaults
                    return self._merge_config(default_config, file_config)
            except Exception as e:
                print(f"Warning: Failed to load config file: {e}")
                return default_config

        return default_config

    def _merge_config(self, default: dict, override: dict) -> dict:
        """Recursively merge configuration dictionaries"""
        result = default.copy()
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._merge_config(result[key], value)
            else:
                result[key] = value
        return result

    @property
    def server_host(self) -> str:
        """Get server host"""
        return os.getenv('DOCKYARD_HOST', self.config['server']['host'])

    @property
    def server_port(self) -> int:
        """Get server port"""
        return int(os.getenv('DOCKYARD_PORT', self.config['server']['port']))

    @property
    def max_workers(self) -> int:
        """Get max workers"""
        return self.config['server']['max_workers']

    @property
    def docker_socket(self) -> str:
        """Get Docker socket"""
        return self.config['docker']['socket']

    @property
    def docker_timeout(self) -> int:
        """Get Docker timeout"""
        return self.config['docker']['timeout']

    @property
    def auth_enabled(self) -> bool:
        """Check if authentication is enabled"""
        return self.config['auth']['enabled']

    @property
    def auth_token(self) -> Optional[str]:
        """Get authentication token from environment"""
        return os.getenv('DOCKYARD_AUTH_TOKEN')

    @property
    def log_level(self) -> str:
        """Get log level"""
        return os.getenv('DOCKYARD_LOG_LEVEL', self.config['logging']['level'])

    @property
    def log_file(self) -> str:
        """Get log file path"""
        return self.config['logging']['file']

    @property
    def log_max_size(self) -> int:
        """Get log max size"""
        return self.config['logging']['max_size']

    @property
    def log_backup_count(self) -> int:
        """Get log backup count"""
        return self.config['logging']['backup_count']
