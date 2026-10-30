"""MySQL/MariaDB query executor."""

import logging
import re

import pymysql
from pymysql.constants import SERVER_STATUS
from pymysql.cursors import DictCursor, SSCursor

from .base import BaseExecutor, QueryResult, MAX_RESULT_ROWS
from ..exceptions import (
    DatabaseConnectionError,
    QueryExecutionError,
    QueryTimeoutError,
    QuerySyntaxError,
)
from ..query_validator import _MYSQL_TOKENS, _strip_sql_comments

logger = logging.getLogger(__name__)

# Statements that start with these keywords return rows and are streamed.
_ROW_QUERY_KEYWORDS = frozenset({'SELECT', 'WITH', 'VALUES', 'TABLE'})
_FIRST_WORD = re.compile(r'[\s(]*([A-Za-z]+)')


def _is_row_query(query: str) -> bool:
    """A single SELECT / WITH / VALUES / TABLE statement, ignoring comments.

    Several statements in one string keep the buffered cursor, so abandoning a
    truncated result can never skip the statements that follow it.
    """
    body = _strip_sql_comments(query, _MYSQL_TOKENS).rstrip('; ')
    if not body or ';' in body:
        return False
    match = _FIRST_WORD.match(body)
    return bool(match) and match.group(1).upper() in _ROW_QUERY_KEYWORDS


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
                # Set query timeout (MariaDB uses max_statement_time in seconds)
                try:
                    cur.execute('SET max_statement_time = %s', [timeout])
                except pymysql.Error:
                    # Fallback for MySQL (uses max_execution_time in milliseconds)
                    try:
                        cur.execute('SET max_execution_time = %s', [timeout * 1000])
                    except pymysql.Error:
                        pass  # If neither works, proceed without timeout

                # Not inside a user transaction: dropping the connection after a
                # truncated result would silently roll it back.
                in_trans = self._connection.server_status & SERVER_STATUS.SERVER_STATUS_IN_TRANS
                if not in_trans and _is_row_query(query):
                    return self._execute_streaming(query)

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

        except pymysql.err.OperationalError as e:
            if 'max_execution_time' in str(e).lower() or e.args[0] == 3024:
                raise QueryTimeoutError(f'Query exceeded {timeout}s timeout')
            error_msg = str(e.args[1]) if len(e.args) > 1 else str(e)
            logger.warning(f'MySQL operational error: {e}')
            return QueryResult(
                success=False,
                error_message=error_msg,
            )
        except pymysql.err.ProgrammingError as e:
            raise QuerySyntaxError(str(e.args[1]) if len(e.args) > 1 else str(e))
        except pymysql.Error as e:
            error_msg = str(e.args[1]) if len(e.args) > 1 else str(e)
            logger.warning(f'MySQL error: {e}')
            return QueryResult(
                success=False,
                error_message=error_msg,
            )

    def _execute_streaming(self, query: str) -> QueryResult:
        """Run a row query on an unbuffered cursor; at most MAX_RESULT_ROWS + 1 rows
        are read off the wire.

        A truncated result is not drained: closing the cursor would read every
        remaining row. The connection is dropped instead (the server abandons the
        result) and a fresh one opened to the same database.
        """
        cur = self._connection.cursor(SSCursor)
        try:
            def run():
                cur.execute(query)
                return cur.fetchmany(MAX_RESULT_ROWS + 1) if cur.description else []

            # Unbuffered rows arrive during the fetch, so both are timed.
            fetched, elapsed_ms = self._measure_time(run)
        except BaseException:
            try:
                cur.close()
            except Exception:
                pass  # a broken socket must not mask the original error
            raise

        if not cur.description:
            affected_rows = cur.rowcount if cur.rowcount >= 0 else 0
            cur.close()
            return QueryResult(
                success=True,
                affected_rows=affected_rows,
                execution_time_ms=elapsed_ms,
            )

        columns = [desc[0] for desc in cur.description]
        rows = [list(row) for row in fetched]
        truncated = len(rows) > MAX_RESULT_ROWS
        if truncated:
            rows = rows[:MAX_RESULT_ROWS]
            self._reconnect()
            # Detach the abandoned result so garbage collection does not try to
            # drain it from the closed socket (SSCursor and MySQLResult both would).
            # These are PyMySQL 1.1 private attributes.
            result = getattr(cur, '_result', None)
            if result is not None:
                result.unbuffered_active = False
            cur._result = None
            cur.connection = None
        else:
            cur.close()
        return QueryResult(
            success=True,
            columns=columns,
            rows=rows,
            row_count=len(rows),
            execution_time_ms=elapsed_ms,
            truncated=truncated,
        )

    def _reconnect(self) -> None:
        """Replace the connection; the rows already read stay valid if this fails."""
        try:
            self._connection.close()
        except Exception:
            pass
        self._connection = None
        try:
            self.connect()
        except DatabaseConnectionError as e:
            logger.warning(f'MySQL reconnect after a truncated result failed: {e}')

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

                # Drop all tables (identifier from SHOW TABLES, not user input)
                for table in tables:
                    safe_name = table.replace('`', '``')
                    cur.execute(f'DROP TABLE IF EXISTS `{safe_name}`')

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
