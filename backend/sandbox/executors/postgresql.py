"""PostgreSQL query executor."""

import psycopg2
from psycopg2 import sql, extensions
from psycopg2.extras import RealDictCursor

from .base import BaseExecutor, QueryResult, MAX_RESULT_ROWS
from ..exceptions import (
    DatabaseConnectionError,
    QueryExecutionError,
    QueryTimeoutError,
    QuerySyntaxError,
)


class PostgreSQLExecutor(BaseExecutor):
    """Executor for PostgreSQL databases."""

    def connect(self) -> None:
        """Establish connection to PostgreSQL."""
        try:
            self._connection = psycopg2.connect(
                host=self.host,
                port=self.port,
                database=self.database,
                user=self.user,
                password=self.password,
                connect_timeout=10,
            )
            self._connection.set_isolation_level(
                extensions.ISOLATION_LEVEL_AUTOCOMMIT
            )
        except psycopg2.Error as e:
            raise DatabaseConnectionError(f'Failed to connect to PostgreSQL: {e}')

    def disconnect(self) -> None:
        """Close PostgreSQL connection."""
        if self._connection:
            try:
                self._connection.close()
            except Exception:
                pass
            self._connection = None

    def is_connected(self) -> bool:
        """Check if PostgreSQL connection is active."""
        if not self._connection:
            return False
        try:
            with self._connection.cursor() as cur:
                cur.execute('SELECT 1')
            return True
        except Exception:
            return False

    def execute_query(self, query: str, timeout: int = 10) -> QueryResult:
        """Execute a SQL query on PostgreSQL."""
        if not self._connection:
            raise DatabaseConnectionError('Not connected to database')

        try:
            with self._connection.cursor() as cur:
                # statement_timeout is set at ROLE level (sandbox_student)
                # Only set as fallback when connecting as admin user
                try:
                    cur.execute(f'SET statement_timeout = {timeout * 1000}')
                except Exception:
                    pass  # ROLE-level timeout takes precedence

                result, elapsed_ms = self._measure_time(cur.execute, query)

                # Check if query returns data
                if cur.description:
                    columns = [desc[0] for desc in cur.description]
                    rows = [list(row) for row in cur.fetchall()]
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
                        affected_rows=cur.rowcount if cur.rowcount >= 0 else 0,
                        execution_time_ms=elapsed_ms,
                    )

        except psycopg2.errors.QueryCanceled:
            raise QueryTimeoutError(f'Query exceeded {timeout}s timeout')
        except psycopg2.errors.SyntaxError as e:
            raise QuerySyntaxError(str(e))
        except psycopg2.Error as e:
            error_msg = str(e).split('\n')[0]  # Get first line of error
            return QueryResult(
                success=False,
                error_message=error_msg,
            )

    def initialize_schema(self, schema_sql: str) -> QueryResult:
        """Initialize PostgreSQL schema."""
        if not schema_sql.strip():
            return QueryResult(success=True)

        try:
            with self._connection.cursor() as cur:
                cur.execute(schema_sql)
            return QueryResult(success=True)
        except psycopg2.Error as e:
            return QueryResult(
                success=False,
                error_message=f'Schema initialization failed: {e}',
            )

    def load_data(self, seed_sql: str) -> QueryResult:
        """Load seed data into PostgreSQL."""
        if not seed_sql.strip():
            return QueryResult(success=True)

        try:
            with self._connection.cursor() as cur:
                cur.execute(seed_sql)
            return QueryResult(success=True)
        except psycopg2.Error as e:
            return QueryResult(
                success=False,
                error_message=f'Data loading failed: {e}',
            )

    def reset(self) -> None:
        """Reset PostgreSQL database by dropping all tables."""
        if not self._connection:
            return

        try:
            with self._connection.cursor() as cur:
                # Get all table names
                cur.execute("""
                    SELECT tablename FROM pg_tables
                    WHERE schemaname = 'public'
                """)
                tables = [row[0] for row in cur.fetchall()]

                # Drop all tables
                for table in tables:
                    cur.execute(
                        sql.SQL('DROP TABLE IF EXISTS {} CASCADE').format(
                            sql.Identifier(table)
                        )
                    )

                # Drop all sequences
                cur.execute("""
                    SELECT sequencename FROM pg_sequences
                    WHERE schemaname = 'public'
                """)
                sequences = [row[0] for row in cur.fetchall()]

                for seq in sequences:
                    cur.execute(
                        sql.SQL('DROP SEQUENCE IF EXISTS {} CASCADE').format(
                            sql.Identifier(seq)
                        )
                    )
        except psycopg2.Error:
            pass  # Ignore reset errors
