"""SQLite query executor."""

import sqlite3

from .base import BaseExecutor, QueryResult, MAX_RESULT_ROWS
from ..exceptions import (
    DatabaseConnectionError,
    QueryTimeoutError,
    QuerySyntaxError,
)


class SQLiteExecutor(BaseExecutor):
    """
    Executor for SQLite databases.

    Uses in-memory database for maximum performance (~100x faster than file-based).
    Each executor instance creates an isolated in-memory database.
    No container or file I/O needed - memory released on disconnect.
    """

    def __init__(self, host: str = '', port: int = 0, database: str = '',
                 user: str = '', password: str = ''):
        super().__init__(host, port, database, user, password)

    def connect(self) -> None:
        """Create an in-memory SQLite database."""
        try:
            self._connection = sqlite3.connect(
                ':memory:',
                timeout=30,
                isolation_level=None,  # Autocommit mode
                check_same_thread=False,  # Allow cross-thread access for sessions
            )
            self._connection.row_factory = sqlite3.Row
        except sqlite3.Error as e:
            raise DatabaseConnectionError(f'Failed to create SQLite database: {e}')

    def disconnect(self) -> None:
        """Close connection - memory is automatically released."""
        if self._connection:
            try:
                self._connection.close()
            except Exception:
                pass
            self._connection = None

    def is_connected(self) -> bool:
        """Check if SQLite connection is active."""
        if not self._connection:
            return False
        try:
            self._connection.execute('SELECT 1')
            return True
        except Exception:
            return False

    def execute_query(self, query: str, timeout: int = 10) -> QueryResult:
        """Execute a SQL query on SQLite."""
        if not self._connection:
            raise DatabaseConnectionError('Not connected to database')

        try:
            cursor = self._connection.cursor()
            result, elapsed_ms = self._measure_time(cursor.execute, query)

            # Check if query returns data
            if cursor.description:
                columns = [desc[0] for desc in cursor.description]
                rows = [list(row) for row in cursor.fetchall()]
                truncated = len(rows) > MAX_RESULT_ROWS
                if truncated:
                    rows = rows[:MAX_RESULT_ROWS]
                return QueryResult(
                    success=True,
                    columns=columns,
                    rows=rows,
                    row_count=len(rows),
                    execution_time_ms=elapsed_ms,
                    truncated=truncated,
                )
            else:
                return QueryResult(
                    success=True,
                    affected_rows=cursor.rowcount if cursor.rowcount >= 0 else 0,
                    execution_time_ms=elapsed_ms,
                )

        except sqlite3.OperationalError as e:
            error_str = str(e).lower()
            if 'syntax error' in error_str or 'near' in error_str:
                raise QuerySyntaxError(str(e))
            return QueryResult(
                success=False,
                error_message=str(e),
            )
        except sqlite3.Error as e:
            return QueryResult(
                success=False,
                error_message=str(e),
            )

    def initialize_schema(self, schema_sql: str) -> QueryResult:
        """Initialize SQLite schema."""
        if not schema_sql.strip():
            return QueryResult(success=True)

        try:
            cursor = self._connection.cursor()
            cursor.executescript(schema_sql)
            return QueryResult(success=True)
        except sqlite3.Error as e:
            return QueryResult(
                success=False,
                error_message=f'Schema initialization failed: {e}',
            )

    def load_data(self, seed_sql: str) -> QueryResult:
        """Load seed data into SQLite."""
        if not seed_sql.strip():
            return QueryResult(success=True)

        try:
            cursor = self._connection.cursor()
            cursor.executescript(seed_sql)
            return QueryResult(success=True)
        except sqlite3.Error as e:
            return QueryResult(
                success=False,
                error_message=f'Data loading failed: {e}',
            )

    def reset(self) -> None:
        """Reset SQLite database by dropping all tables."""
        if not self._connection:
            return

        try:
            cursor = self._connection.cursor()

            # Get all table names
            cursor.execute("""
                SELECT name FROM sqlite_master
                WHERE type='table' AND name NOT LIKE 'sqlite_%'
            """)
            tables = [row[0] for row in cursor.fetchall()]

            # Drop all tables
            for table in tables:
                cursor.execute(f'DROP TABLE IF EXISTS "{table}"')

        except sqlite3.Error:
            pass  # Ignore reset errors
