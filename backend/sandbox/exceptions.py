"""Custom exceptions for the sandbox module."""


class SandboxError(Exception):
    """Base exception for sandbox errors."""
    pass


class ContainerError(SandboxError):
    """Error related to container operations."""
    pass


class ContainerStartError(ContainerError):
    """Container failed to start."""
    pass


class ContainerTimeoutError(ContainerError):
    """Container operation timed out."""
    pass


class NoAvailableContainerError(ContainerError):
    """No container available in the pool."""
    pass


class QueryExecutionError(SandboxError):
    """Error during query execution."""
    pass


class QueryTimeoutError(QueryExecutionError):
    """Query execution timed out."""
    pass


class QuerySyntaxError(QueryExecutionError):
    """Query has syntax errors."""
    pass


class DatabaseConnectionError(SandboxError):
    """Failed to connect to database."""
    pass


class DatasetInitializationError(SandboxError):
    """Failed to initialize dataset in container."""
    pass
