"""
Docker utilities for Dockyard Agent
"""
from typing import Dict, List
from datetime import datetime


def format_ports(port_bindings: Dict) -> str:
    """Format port bindings for display

    Args:
        port_bindings: Docker port bindings dict

    Returns:
        Formatted port string
    """
    if not port_bindings:
        return ""

    ports = []
    for container_port, host_bindings in port_bindings.items():
        if host_bindings:
            for binding in host_bindings:
                host_ip = binding.get('HostIp', '0.0.0.0')
                host_port = binding.get('HostPort', '')
                if host_ip == '0.0.0.0':
                    ports.append(f"{host_port}->{container_port}")
                else:
                    ports.append(f"{host_ip}:{host_port}->{container_port}")
        else:
            ports.append(container_port)

    return ", ".join(ports)


def format_timestamp(timestamp: str) -> str:
    """Format ISO timestamp for display

    Args:
        timestamp: ISO format timestamp

    Returns:
        Formatted timestamp string
    """
    try:
        # Parse ISO format
        dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        return dt.strftime('%Y-%m-%d %H:%M:%S')
    except Exception:
        return timestamp


def format_bytes(bytes_value: int) -> str:
    """Format bytes to human-readable format

    Args:
        bytes_value: Number of bytes

    Returns:
        Human-readable string (e.g., "1.5 GB")
    """
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_value < 1024.0:
            return f"{bytes_value:.1f}{unit}"
        bytes_value /= 1024.0
    return f"{bytes_value:.1f}PB"


def truncate_string(s: str, max_length: int = 30) -> str:
    """Truncate string if it exceeds max length

    Args:
        s: Input string
        max_length: Maximum length

    Returns:
        Truncated string with ellipsis if needed
    """
    if len(s) <= max_length:
        return s
    return s[:max_length - 3] + "..."


def parse_environment(env_list: List[str]) -> Dict[str, str]:
    """Parse environment variable list to dictionary

    Args:
        env_list: List of "KEY=VALUE" strings

    Returns:
        Dictionary of environment variables
    """
    env_dict = {}
    for item in env_list:
        if '=' in item:
            key, value = item.split('=', 1)
            env_dict[key] = value
    return env_dict


def build_environment_list(env_dict: Dict[str, str]) -> List[str]:
    """Build environment variable list from dictionary

    Args:
        env_dict: Dictionary of environment variables

    Returns:
        List of "KEY=VALUE" strings
    """
    return [f"{key}={value}" for key, value in env_dict.items()]
