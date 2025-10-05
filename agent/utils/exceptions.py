"""
Custom exceptions for Dockyard Agent
"""


class DockyardException(Exception):
    """Base exception for Dockyard"""
    pass


class DockerClientException(DockyardException):
    """Docker client related exceptions"""
    pass


class ContainerNotFoundException(DockerClientException):
    """Container not found exception"""
    pass


class ContainerOperationException(DockerClientException):
    """Container operation failed exception"""
    pass


class ImageNotFoundException(DockerClientException):
    """Image not found exception"""
    pass


class AuthenticationException(DockyardException):
    """Authentication related exceptions"""
    pass


class ConfigurationException(DockyardException):
    """Configuration related exceptions"""
    pass


class ServiceException(DockyardException):
    """Service layer exceptions"""
    pass
