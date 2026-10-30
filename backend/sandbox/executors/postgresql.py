"""PostgreSQL query executor."""

import logging
import re
import time
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


# A script containing any of these keeps the plain multi-statement execute: running
# it piece by piece inside our own transaction would change what they do.
_TRANSACTION_CONTROL = frozenset({
    'BEGIN', 'START', 'COMMIT', 'END', 'ROLLBACK', 'ABORT', 'SAVEPOINT', 'RELEASE', 'PREPARE',
})
# Left over outside every recognised token, these mean the tokenizer may have
# misread the text (nested /* */, "$" inside a bare identifier, an unclosed quote).
# Two contrived inputs still get past this check: a nested comment whose outer
# close sits inside a later literal, and the same $x$ appearing in two bare
# identifiers (read as one dollar quote). Both fail safe: the text is taken as
# fewer statements than it holds, so it ends in a server-side syntax error or a
# result capped like any other; nothing is split inside a literal.
_UNSAFE_LEFTOVERS = ("'", '"', '$', '/*', '*/')
_SAVEPOINT = 'sandbox_cursor'


def _first_keyword(statement: str) -> str:
    match = _FIRST_WORD.match(_strip_sql_comments(statement, _STANDARD_TOKENS))
    return match.group(1).upper() if match else ''


def _is_row_query(query: str) -> bool:
    """A single SELECT / WITH / VALUES / TABLE statement, ignoring comments.

    Several statements in one string are not a row query: they are split by
    _split_statements and run as a script.
    """
    body = _strip_sql_comments(query, _STANDARD_TOKENS).rstrip('; ')
    if not body or ';' in body:
        return False
    return _first_keyword(body) in _ROW_QUERY_KEYWORDS


def _split_statements(query: str) -> list[str] | None:
    """Slice the original text at top-level semicolons, using the validator's
    tokenizer so literals, comments and dollar quotes stay intact.

    Pieces that are empty or only comments are dropped. Returns None when the
    tokenization cannot be trusted, or when a semicolon sits inside parentheses
    (CREATE RULE ... DO (a; b) is one statement) or they do not balance; the
    caller then keeps the plain execute.
    """
    pieces = []
    start = 0
    gap_start = 0
    depth = 0
    matches = list(_STANDARD_TOKENS.finditer(query))
    for gap_end, next_start in [(m.start(), m.end()) for m in matches] + [(len(query), len(query))]:
        gap = query[gap_start:gap_end]
        if any(mark in gap for mark in _UNSAFE_LEFTOVERS):
            return None
        for offset, char in enumerate(gap):
            if char == '(':
                depth += 1
            elif char == ')':
                depth -= 1
                if depth < 0:
                    return None
            elif char == ';':
                if depth:
                    return None
                pieces.append(query[start:gap_start + offset])
                start = gap_start + offset + 1
        gap_start = next_start
    if depth:
        return None
    pieces.append(query[start:])
    return [piece.strip() for piece in pieces if _strip_sql_comments(piece, _STANDARD_TOKENS)]


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

                # A session user may have run BEGIN: then nothing here may commit,
                # roll back or change autocommit. A failed transaction (INERROR)
                # rejects every statement anyway and keeps the plain path.
                status = self._connection.info.transaction_status
                idle = status == extensions.TRANSACTION_STATUS_IDLE
                if idle or status == extensions.TRANSACTION_STATUS_INTRANS:
                    pieces = _split_statements(query)
                    if pieces is not None and len(pieces) > 1:
                        if not any(_first_keyword(p) in _TRANSACTION_CONTROL for p in pieces):
                            return self._execute_script(cur, pieces, own_transaction=idle)
                    elif _is_row_query(query):
                        if idle:
                            try:
                                return self._execute_streaming(query)
                            except _DECLARE_REJECTED:
                                pass  # run it as a plain statement below
                        else:
                            result = self._stream_in_transaction(cur, query)
                            if result is not None:
                                return result

                return self._execute_plain(cur, query)

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

    def _execute_plain(self, cur, query: str) -> QueryResult:
        """Execute on a client-side cursor; the whole result is transferred."""
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

    def _stream_in_transaction(self, cur, query: str, fetch: bool = True) -> QueryResult | None:
        """Stream a row query inside an already open transaction without ending it.

        psycopg2 refuses its own named cursors while autocommit is on, so the
        cursor is declared in SQL. A savepoint keeps a rejected DECLARE (SELECT ...
        INTO, data-modifying WITH) from aborting the transaction: it is rolled back
        to and None is returned, and the caller runs the statement plainly. With
        fetch=False the rows are skipped on the server (MOVE), for script
        statements whose result is discarded.
        """
        name = f'sandbox_fetch_{uuid.uuid4().hex[:12]}'
        cur.execute(f'SAVEPOINT {_SAVEPOINT}')
        start = time.perf_counter()
        try:
            cur.execute(f'DECLARE "{name}" NO SCROLL CURSOR FOR {query}')
        except _DECLARE_REJECTED:
            cur.execute(f'ROLLBACK TO SAVEPOINT {_SAVEPOINT}')
            cur.execute(f'RELEASE SAVEPOINT {_SAVEPOINT}')
            return None
        if fetch:
            cur.execute(f'FETCH FORWARD {MAX_RESULT_ROWS + 1} FROM "{name}"')
            columns = [desc[0] for desc in cur.description] if cur.description else []
            rows = [list(row) for row in cur.fetchall()]
        else:
            cur.execute(f'MOVE FORWARD ALL IN "{name}"')
            columns, rows = [], []
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        cur.execute(f'CLOSE "{name}"')
        cur.execute(f'RELEASE SAVEPOINT {_SAVEPOINT}')

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

    def _execute_script(self, cur, pieces: list[str], own_transaction: bool) -> QueryResult:
        """Run several statements one by one; the result is the last statement's.

        A single multi-statement execute ran as one implicit transaction, so when
        no user transaction is open the pieces run inside BEGIN ... COMMIT and any
        error rolls all of them back. Inside a user transaction they simply run in
        it. Row queries stream: the last one is fetched up to the cap, earlier ones
        are skipped on the server.
        """
        start = time.perf_counter()
        if own_transaction:
            cur.execute('BEGIN')
        try:
            for piece in pieces[:-1]:
                if not (_is_row_query(piece)
                        and self._stream_in_transaction(cur, piece, fetch=False)):
                    cur.execute(piece)
            last = pieces[-1]
            result = self._stream_in_transaction(cur, last) if _is_row_query(last) else None
            if result is None:
                result = self._execute_plain(cur, last)
            if own_transaction:
                cur.execute('COMMIT')
        except BaseException:
            if own_transaction:
                try:
                    cur.execute('ROLLBACK')
                except Exception:
                    pass  # a broken connection must not mask the original error
            raise
        result.execution_time_ms = int((time.perf_counter() - start) * 1000)
        return result

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
            try:
                if not conn.closed:
                    conn.autocommit = True
            except Exception:
                pass  # a broken connection must not mask the original error

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
