"""Redis query executor."""

import redis
import json
import shlex

from .base import BaseExecutor, QueryResult
from ..exceptions import (
    DatabaseConnectionError,
    QueryTimeoutError,
    QuerySyntaxError,
)


class RedisExecutor(BaseExecutor):
    """Executor for Redis databases."""

    def __init__(self, host: str, port: int, database: str = '0',
                 user: str = '', password: str = ''):
        super().__init__(host, port, database, user, password)
        self._client = None

    def connect(self) -> None:
        """Establish connection to Redis."""
        try:
            db_number = int(self.database) if self.database.isdigit() else 0
            self._client = redis.Redis(
                host=self.host,
                port=self.port,
                db=db_number,
                decode_responses=True,
                socket_timeout=10,
                socket_connect_timeout=10,
            )
            # Test connection
            self._client.ping()
        except redis.RedisError as e:
            raise DatabaseConnectionError(f'Failed to connect to Redis: {e}')

    def disconnect(self) -> None:
        """Close Redis connection."""
        if self._client:
            try:
                self._client.close()
            except Exception:
                pass
            self._client = None

    def is_connected(self) -> bool:
        """Check if Redis connection is active."""
        if not self._client:
            return False
        try:
            self._client.ping()
            return True
        except Exception:
            return False

    def execute_query(self, query: str, timeout: int = 10) -> QueryResult:
        """Execute a Redis command.

        Query format examples:
        - SET key value
        - GET key
        - HSET user:1 name "John"
        - LPUSH mylist "item1" "item2"
        """
        if not self._client:
            raise DatabaseConnectionError('Not connected to database')

        try:
            # Parse command and arguments
            parts = self._parse_command(query)
            if not parts:
                raise QuerySyntaxError('Empty command')

            command = parts[0].upper()
            args = parts[1:]

            # Execute command with timeout
            result, elapsed_ms = self._measure_time(
                self._execute_command,
                command,
                args,
                timeout
            )

            # Format result
            return self._format_result(result, elapsed_ms)

        except redis.TimeoutError:
            raise QueryTimeoutError(f'Query exceeded {timeout}s timeout')
        except redis.ResponseError as e:
            return QueryResult(
                success=False,
                error_message=str(e),
            )
        except redis.RedisError as e:
            return QueryResult(
                success=False,
                error_message=str(e),
            )

    def _parse_command(self, query: str) -> list[str]:
        """Parse Redis command string into parts."""
        query = query.strip()
        if not query:
            return []

        try:
            return shlex.split(query)
        except ValueError:
            # Fallback to simple split if shlex fails
            return query.split()

    def _execute_command(self, command: str, args: list, timeout: int):
        """Execute a Redis command."""
        # Set socket timeout for this command
        self._client.connection_pool.connection_kwargs['socket_timeout'] = timeout

        # Execute the command
        return self._client.execute_command(command, *args)

    def _format_result(self, result, elapsed_ms: int) -> QueryResult:
        """Format Redis command result."""
        if result is None:
            return QueryResult(
                success=True,
                columns=['result'],
                rows=[['(nil)']],
                row_count=1,
                execution_time_ms=elapsed_ms,
            )

        if isinstance(result, bool):
            return QueryResult(
                success=True,
                columns=['result'],
                rows=[['OK' if result else '(error)']],
                row_count=1,
                execution_time_ms=elapsed_ms,
            )

        if isinstance(result, (int, float)):
            return QueryResult(
                success=True,
                columns=['result'],
                rows=[[str(result)]],
                row_count=1,
                execution_time_ms=elapsed_ms,
            )

        if isinstance(result, str):
            return QueryResult(
                success=True,
                columns=['result'],
                rows=[[result]],
                row_count=1,
                execution_time_ms=elapsed_ms,
            )

        if isinstance(result, bytes):
            return QueryResult(
                success=True,
                columns=['result'],
                rows=[[result.decode('utf-8', errors='replace')]],
                row_count=1,
                execution_time_ms=elapsed_ms,
            )

        if isinstance(result, list):
            rows = [[json.dumps(item) if not isinstance(item, (str, int, float, type(None))) else str(item)]
                    for item in result]
            return QueryResult(
                success=True,
                columns=['result'],
                rows=rows if rows else [['(empty list)']],
                row_count=len(rows),
                execution_time_ms=elapsed_ms,
            )

        if isinstance(result, dict):
            rows = [[k, json.dumps(v) if not isinstance(v, (str, int, float, type(None))) else str(v)]
                    for k, v in result.items()]
            return QueryResult(
                success=True,
                columns=['key', 'value'],
                rows=rows if rows else [['(empty hash)', '']],
                row_count=len(rows),
                execution_time_ms=elapsed_ms,
            )

        if isinstance(result, set):
            rows = [[str(item)] for item in result]
            return QueryResult(
                success=True,
                columns=['member'],
                rows=rows if rows else [['(empty set)']],
                row_count=len(rows),
                execution_time_ms=elapsed_ms,
            )

        # Default: convert to JSON
        return QueryResult(
            success=True,
            columns=['result'],
            rows=[[json.dumps(result)]],
            row_count=1,
            execution_time_ms=elapsed_ms,
        )

    def initialize_schema(self, schema_sql: str) -> QueryResult:
        """Initialize Redis (execute setup commands)."""
        if not schema_sql.strip():
            return QueryResult(success=True)

        try:
            for line in schema_sql.strip().split('\n'):
                line = line.strip()
                if line and not line.startswith('#'):
                    self.execute_query(line, timeout=30)
            return QueryResult(success=True)
        except Exception as e:
            return QueryResult(
                success=False,
                error_message=f'Schema initialization failed: {e}',
            )

    def load_data(self, seed_sql: str) -> QueryResult:
        """Load seed data into Redis."""
        if not seed_sql.strip():
            return QueryResult(success=True)

        try:
            for line in seed_sql.strip().split('\n'):
                line = line.strip()
                if line and not line.startswith('#'):
                    self.execute_query(line, timeout=30)
            return QueryResult(success=True)
        except Exception as e:
            return QueryResult(
                success=False,
                error_message=f'Data loading failed: {e}',
            )

    def reset(self) -> None:
        """Reset Redis by flushing the database."""
        if not self._client:
            return

        try:
            self._client.flushdb()
        except redis.RedisError:
            pass  # Ignore reset errors
