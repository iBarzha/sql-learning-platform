"""PostgreSQL query executor."""

import logging
import re
import uuid

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
from ..query_validator import _STANDARD_TOKENS, _strip_sql_comments

logger = logging.getLogger(__name__)

# Statements that start with these keywords return rows and are streamed.
_ROW_QUERY_KEYWORDS = frozenset({'SELECT', 'WITH', 'VALUES', 'TABLE'})
_FIRST_WORD = re.compile(r'[\s(]*([A-Za-z]+)')

# DECLARE refuses some row queries that run fine on their own (SELECT ... INTO,
# data-modifying WITH, FOR UPDATE ...). Nothing has executed yet, so these are
# retried once on the plain cursor, which also reports real syntax errors as before.
_DECLARE_REJECTED = (
    psycopg2.errors.SyntaxError,
    psycopg2.errors.FeatureNotSupported,
    psycopg2.errors.InvalidCursorDefinition,
)


def _is_row_query(query: str) -> bool:
    """A single SELECT / WITH / VALUES / TABLE statement, ignoring comments.

    Several statements in one string keep the plain cursor: DECLARE would take
    only the first of them, while the plain cursor returns the last result.
    """
    body = _strip_sql_comments(query, _STANDARD_TOKENS).rstrip('; ')
    if not body or ';' in body:
        return False
    match = _FIRST_WORD.match(body)
    return bool(match) and match.group(1).upper() in _ROW_QUERY_KEYWORDS


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
                    cur.execute('SET statement_timeout = %s', [timeout * 1000])
                except Exception:
                    pass  # ROLE-level timeout takes precedence

                if _is_row_query(query):
                    try:
                        return self._execute_streaming(query)
                    except _DECLARE_REJECTED:
                        pass  # run it as a plain statement below

                result, elapsed_ms = self._measure_time(cur.execute, query)

                # Check if query returns data
                if cur.description:
                    columns = [desc[0] for desc in cur.description]
                    rows = [list(row) for row in cur.fetchmany(MAX_RESULT_ROWS + 1)]
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
            logger.warning(f'PostgreSQL query error: {e}')
            error_msg = str(e).split('\n')[0]  # Get first line of error
            return QueryResult(
                success=False,
                error_message=error_msg,
            )

    def _execute_streaming(self, query: str) -> QueryResult:
        """Run a row query through a server-side cursor; at most MAX_RESULT_ROWS + 1
        rows ever leave the server.

        The cursor lives in a short explicit transaction rather than WITH HOLD in
        autocommit: a holdable cursor is materialised in full at the implicit commit,
        after statement_timeout has already been disarmed, so a huge join would run
        unbounded on the server. Here the DECLARE and the FETCH are each ordinary
        statements under statement_timeout, and only the fetched rows are computed
        when the plan allows it. The transaction is committed, as autocommit would
        have done, and autocommit is restored whatever happens.
        """
        conn = self._connection
        conn.autocommit = False
        try:
            cur = conn.cursor(name=f'sandbox_fetch_{uuid.uuid4().hex[:12]}')
            cur.itersize = MAX_RESULT_ROWS + 1

            def run():
                cur.execute(query)
                return cur.fetchmany(MAX_RESULT_ROWS + 1)

            # The rows are computed during FETCH, so both statements are timed.
            fetched, elapsed_ms = self._measure_time(run)
            # A named cursor learns its columns from the first FETCH.
            columns = [desc[0] for desc in cur.description] if cur.description else []
            cur.close()
            conn.commit()
        except BaseException:
            try:
                conn.rollback()
            except psycopg2.Error:
                pass
            raise
        finally:
            if not conn.closed:
                conn.autocommit = True

        rows = [list(row) for row in fetched]
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
