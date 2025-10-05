"""
Formatting utilities for Dockyard CLI
"""


def format_bytes(bytes_value: int) -> str:
    """Format bytes to human-readable format

    Args:
        bytes_value: Number of bytes

    Returns:
        Human-readable string (e.g., "1.5GB")
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


def clear_screen():
    """Clear terminal screen"""
    import os
    os.system('cls' if os.name == 'nt' else 'clear')


def move_cursor_up(lines: int = 1):
    """Move cursor up by specified lines

    Args:
        lines: Number of lines to move up
    """
    print(f'\033[{lines}A', end='')


def clear_line():
    """Clear current line"""
    print('\033[2K', end='')


def hide_cursor():
    """Hide terminal cursor"""
    print('\033[?25l', end='')


def show_cursor():
    """Show terminal cursor"""
    print('\033[?25h', end='')
