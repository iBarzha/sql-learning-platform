"""Database query executors."""

from .base import BaseExecutor, QueryResult
from .postgresql import PostgreSQLExecutor
from .mysql import MySQLExecutor
from .mongodb import MongoDBExecutor
from .redis_executor import RedisExecutor

__all__ = [
    'BaseExecutor',
    'QueryResult',
    'PostgreSQLExecutor',
    'MySQLExecutor',
    'MongoDBExecutor',
    'RedisExecutor',
]


def get_executor(database_type: str) -> type[BaseExecutor]:
    """Get the executor class for a database type."""
    executors = {
        'postgresql': PostgreSQLExecutor,
        'mysql': MySQLExecutor,
        'mariadb': MySQLExecutor,  # MariaDB uses MySQL protocol
        'mongodb': MongoDBExecutor,
        'redis': RedisExecutor,
    }
    executor_class = executors.get(database_type)
    if not executor_class:
        raise ValueError(f'Unsupported database type: {database_type}')
    return executor_class
