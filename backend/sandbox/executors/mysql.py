"""MySQL/MariaDB query executor."""

import pymysql
from pymysql.cursors import DictCursor

from .base import BaseExecutor, QueryResult
from ..exceptions import (
    DatabaseConnectionError,
    QueryExecutionError,
    QueryTimeoutError,
    QuerySyntaxError,
)


class MySQLExecutor(BaseExecutor):
    """Executor for MySQL and MariaDB databases."""

    def connect(self) -> None:
        """Establish connection to MySQL/MariaDB."""
        try:
            self._connection = pymysql.connect(
                host=self.host,
                port=self.port,
                database=self.database,
                user=self.user,
                password=self.password,
                connect_timeout=10,
                read_timeout=30,
                write_timeout=30,
                autocommit=True,
            )
        except pymysql.Error as e:
            raise DatabaseConnectionError(f'Failed to connect to MySQL: {e}')

    def disconnect(self) -> None:
        """Close MySQL connection."""
        if self._connection:
            try:
                self._connection.close()
            except Exception:
                pass
            self._connection = None

    def is_connected(self) -> bool:
        """Check if MySQL connection is active."""
        if not self._connection:
            return False
        try:
            self._connection.ping(reconnect=False)
            return True
        except Exception:
            return False

    def execute_query(self, query: str, timeout: int = 10) -> QueryResult:
        """Execute a SQL query on MySQL/MariaDB."""
        if not self._connection:
            raise DatabaseConnectionError('Not connected to database')

        try:
            with self._connection.cursor() as cur:
                # Set query timeout (max_execution_time in milliseconds)
                cur.execute(f'SET max_execution_time = {timeout * 1000}')

                result, elapsed_ms = self._measure_time(cur.execute, query)

                # Check if query returns data
                if cur.description:
                    columns = [desc[0] for desc in cur.description]
                    rows = [list(row) for row in cur.fetchall()]
                    return QueryResult(
                        success=True,
                        columns=columns,
                        rows=rows,
                        row_count=len(rows),
                        execution_time_ms=elapsed_ms,
                    )
                else:
                    return QueryResult(
                        success=True,
                        affected_rows=cur.rowcount if cur.rowcount >= 0 else 0,
                        execution_time_ms=elapsed_ms,
                    )

        except pymysql.err.OperationalError as e:
            if 'max_execution_time' in str(e).lower() or e.args[0] == 3024:
                raise QueryTimeoutError(f'Query exceeded {timeout}s timeout')
            return QueryResult(
                success=False,
                error_message=str(e.args[1]) if len(e.args) > 1 else str(e),
            )
        except pymysql.err.ProgrammingError as e:
            raise QuerySyntaxError(str(e.args[1]) if len(e.args) > 1 else str(e))
        except pymysql.Error as e:
            error_msg = str(e.args[1]) if len(e.args) > 1 else str(e)
            return QueryResult(
                success=False,
                error_message=error_msg,
            )

    def initialize_schema(self, schema_sql: str) -> QueryResult:
        """Initialize MySQL schema."""
        if not schema_sql.strip():
            return QueryResult(success=True)

        try:
            with self._connection.cursor() as cur:
                # Execute multi-statement schema
                for statement in self._split_statements(schema_sql):
                    if statement.strip():
                        cur.execute(statement)
            return QueryResult(success=True)
        except pymysql.Error as e:
            return QueryResult(
                success=False,
                error_message=f'Schema initialization failed: {e}',
            )

    def load_data(self, seed_sql: str) -> QueryResult:
        """Load seed data into MySQL."""
        if not seed_sql.strip():
            return QueryResult(success=True)

        try:
            with self._connection.cursor() as cur:
                for statement in self._split_statements(seed_sql):
                    if statement.strip():
                        cur.execute(statement)
            return QueryResult(success=True)
        except pymysql.Error as e:
            return QueryResult(
                success=False,
                error_message=f'Data loading failed: {e}',
            )

    def reset(self) -> None:
        """Reset MySQL database by dropping all tables."""
        if not self._connection:
            return

        try:
            with self._connection.cursor() as cur:
                # Disable foreign key checks
                cur.execute('SET FOREIGN_KEY_CHECKS = 0')

                # Get all table names
                cur.execute(f'SHOW TABLES')
                tables = [row[0] for row in cur.fetchall()]

                # Drop all tables
                for table in tables:
                    cur.execute(f'DROP TABLE IF EXISTS `{table}`')

                # Re-enable foreign key checks
                cur.execute('SET FOREIGN_KEY_CHECKS = 1')
        except pymysql.Error:
            pass  # Ignore reset errors

    @staticmethod
    def _split_statements(sql: str) -> list[str]:
        """Split SQL into individual statements."""
        statements = []
        current = []
        in_string = False
        string_char = None

        for char in sql:
            if char in ('"', "'") and not in_string:
                in_string = True
                string_char = char
            elif char == string_char and in_string:
                in_string = False
                string_char = None

            if char == ';' and not in_string:
                statements.append(''.join(current))
                current = []
            else:
                current.append(char)

        if current:
            statements.append(''.join(current))

        return [s.strip() for s in statements if s.strip()]
