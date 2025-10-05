"""
Custom exceptions for Dockyard CLI
"""


class CLIException(Exception):
    """Base exception for CLI"""
    pass


class ConnectionException(CLIException):
    """Connection related exceptions"""
    pass


class AuthenticationException(CLIException):
    """Authentication related exceptions"""
    pass


class ConfigurationException(CLIException):
    """Configuration related exceptions"""
    pass


class CommandException(CLIException):
    """Command execution exceptions"""
    pass


class ValidationException(CLIException):
    """Input validation exceptions"""
    pass
