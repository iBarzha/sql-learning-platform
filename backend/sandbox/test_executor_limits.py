"""Row cap tests for the executors.

SQLite runs in-process. PostgreSQL and MariaDB run against faked driver
objects here; the real engines are covered by test_grading_engines.py.
"""
from unittest import mock

import psycopg2
import pymysql
from django.test import SimpleTestCase

from sandbox.exceptions import QueryTimeoutError
from sandbox.executors.base import MAX_RESULT_ROWS
from sandbox.executors.mysql import MySQLExecutor
from sandbox.executors.postgresql import PostgreSQLExecutor
from sandbox.executors.sqlite import SQLiteExecutor


def _series(n):
    return (
        f'WITH RECURSIVE n(x) AS (SELECT 1 UNION ALL SELECT x + 1 FROM n WHERE x < {n}) '
        'SELECT x FROM n'
    )


class SqliteRowCapTests(SimpleTestCase):
    def setUp(self):
        self.executor = SQLiteExecutor()
        self.executor.connect()
        self.addCleanup(self.executor.disconnect)

    def test_over_limit_is_capped_and_truncated(self):
        result = self.executor.execute_query(_series(2500))
        self.assertTrue(result.success)
        self.assertEqual(len(result.rows), MAX_RESULT_ROWS)
        self.assertEqual(result.row_count, MAX_RESULT_ROWS)
        self.assertTrue(result.truncated)

    def test_exactly_limit_is_not_truncated(self):
        result = self.executor.execute_query(_series(MAX_RESULT_ROWS))
        self.assertEqual(len(result.rows), MAX_RESULT_ROWS)
        self.assertFalse(result.truncated)

    def test_one_over_limit_is_truncated(self):
        result = self.executor.execute_query(_series(MAX_RESULT_ROWS + 1))
        self.assertEqual(len(result.rows), MAX_RESULT_ROWS)
        self.assertTrue(result.truncated)


# ---------------------------------------------------------------------------
# Streaming on PostgreSQL and MariaDB, with only the driver objects faked.
# ---------------------------------------------------------------------------


class _FakePgPlainCursor:
    """psycopg2 client-side cursor: everything arrives during execute()."""

    def __init__(self, conn):
        self.conn = conn
        self.description = None
        self.rowcount = -1
        self._rows = []

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, query, params=None):
        self.conn.log.append(('plain', query))
        if query.startswith('SET '):
            return
        result = self.conn.plain_result
        if result is None:
            self.rowcount = self.conn.plain_rowcount
        else:
            self.description = [(c,) for c in result[0]]
            self._rows = list(result[1])
            self.rowcount = len(self._rows)

    def fetchmany(self, size):
        rows, self._rows = self._rows[:size], self._rows[size:]
        return rows


class _FakePgNamedCursor:
    """psycopg2 named cursor: DECLARE on execute, description known after FETCH."""

    def __init__(self, conn, name, withhold):
        self.conn = conn
        self.name = name
        self.withhold = withhold
        self.itersize = 2000
        self.description = None
        self.closed = False
        self.fetch_sizes = []

    def execute(self, query, params=None):
        self.conn.log.append(('declare', query, self.conn.autocommit))
        if self.conn.declare_error is not None:
            raise self.conn.declare_error

    def fetchmany(self, size):
        self.fetch_sizes.append(size)
        if self.conn.fetch_error is not None:
            raise self.conn.fetch_error
        columns, rows = self.conn.named_result
        self.description = [(c,) for c in columns]
        return list(rows[:size])

    def close(self):
        self.closed = True
        self.conn.log.append(('close', self.name))


class _FakePgConnection:
    def __init__(self, named_result=None, plain_result=None, plain_rowcount=0,
                 declare_error=None, fetch_error=None):
        self.autocommit = True
        self.closed = 0
        self.named_result = named_result
        self.plain_result = plain_result
        self.plain_rowcount = plain_rowcount
        self.declare_error = declare_error
        self.fetch_error = fetch_error
        self.log = []
        self.named = []

    def cursor(self, name=None, withhold=False):
        if name is None:
            return _FakePgPlainCursor(self)
        cur = _FakePgNamedCursor(self, name, withhold)
        self.named.append(cur)
        return cur

    def commit(self):
        self.log.append(('commit',))

    def rollback(self):
        self.log.append(('rollback',))


def _numbers(n):
    return [(i,) for i in range(1, n + 1)]


class PostgresStreamingTests(SimpleTestCase):
    def run_query(self, query, **conn_kwargs):
        executor = PostgreSQLExecutor('fake-host', 5432)
        executor._connection = _FakePgConnection(**conn_kwargs)
        return executor, executor._connection, executor.execute_query(query, timeout=5)

    def plain_queries(self, conn):
        return [e[1] for e in conn.log if e[0] == 'plain' and not e[1].startswith('SET ')]

    def test_select_streams_through_a_named_cursor(self):
        _, conn, result = self.run_query(
            'SELECT x FROM t', named_result=(['x'], _numbers(2500)))
        self.assertEqual(len(conn.named), 1)
        cur = conn.named[0]
        self.assertFalse(cur.withhold)   # WITH HOLD would run the query outside statement_timeout
        self.assertEqual(cur.itersize, MAX_RESULT_ROWS + 1)
        self.assertEqual(cur.fetch_sizes, [MAX_RESULT_ROWS + 1])
        self.assertTrue(cur.closed)
        self.assertEqual(self.plain_queries(conn), [])
        self.assertTrue(result.success)
        self.assertEqual(result.columns, ['x'])
        self.assertEqual(len(result.rows), MAX_RESULT_ROWS)
        self.assertEqual(result.row_count, MAX_RESULT_ROWS)
        self.assertEqual(result.rows[0], [1])
        self.assertTrue(result.truncated)

    def test_cursor_lives_in_a_transaction_and_autocommit_is_restored(self):
        _, conn, _ = self.run_query('SELECT 1', named_result=(['?column?'], [(1,)]))
        declare = [e for e in conn.log if e[0] == 'declare'][0]
        self.assertFalse(declare[2])
        kinds = [e[0] for e in conn.log]
        self.assertLess(kinds.index('close'), kinds.index('commit'))
        self.assertTrue(conn.autocommit)

    def test_query_classes_that_stream(self):
        for query in ('select 1', '  WITH a AS (SELECT 1) SELECT * FROM a', 'VALUES (1)',
                      'TABLE t', '-- note\nSELECT 1', '/* a */ /* b */ SELECT 1;',
                      '((SELECT 1) EXCEPT ALL (SELECT 2)) UNION ALL ((SELECT 2) EXCEPT ALL (SELECT 1))'):
            with self.subTest(query=query):
                _, conn, result = self.run_query(query, named_result=(['c'], [(1,)]))
                self.assertEqual(len(conn.named), 1)
                self.assertTrue(result.success)

    def test_other_statements_keep_the_plain_cursor(self):
        for query in ('UPDATE t SET x = 1', 'INSERT INTO t VALUES (1)', 'EXPLAIN SELECT 1',
                      'SHOW search_path', "SELECT 'a;b'; SELECT 2", '-- SELECT\nDELETE FROM t'):
            with self.subTest(query=query):
                _, conn, _ = self.run_query(query, plain_rowcount=3)
                self.assertEqual(conn.named, [])
                self.assertEqual(self.plain_queries(conn), [query])

    def test_dml_reports_affected_rows(self):
        _, conn, result = self.run_query('DELETE FROM t', plain_rowcount=4)
        self.assertEqual(result.affected_rows, 4)
        self.assertEqual(result.columns, [])
        self.assertFalse(result.truncated)

    def test_empty_select_keeps_columns(self):
        _, _, result = self.run_query('SELECT a, b FROM t WHERE false',
                                      named_result=(['a', 'b'], []))
        self.assertTrue(result.success)
        self.assertEqual(result.columns, ['a', 'b'])
        self.assertEqual(result.rows, [])
        self.assertFalse(result.truncated)

    def test_declare_rejection_falls_back_to_the_plain_cursor_once(self):
        for error in (psycopg2.errors.SyntaxError('SELECT ... INTO is not allowed here'),
                      psycopg2.errors.FeatureNotSupported('data-modifying WITH')):
            with self.subTest(error=type(error).__name__):
                _, conn, result = self.run_query(
                    'SELECT 1 INTO t2', declare_error=error, plain_rowcount=1)
                self.assertEqual(len([e for e in conn.log if e[0] == 'declare']), 1)
                self.assertIn(('rollback',), conn.log)
                self.assertTrue(conn.autocommit)
                self.assertEqual(self.plain_queries(conn), ['SELECT 1 INTO t2'])
                self.assertTrue(result.success)
                self.assertEqual(result.affected_rows, 1)

    def test_timeout_while_fetching_maps_to_query_timeout(self):
        executor = PostgreSQLExecutor('fake-host', 5432)
        executor._connection = conn = _FakePgConnection(
            named_result=(['x'], []), fetch_error=psycopg2.errors.QueryCanceled('timeout'))
        with self.assertRaises(QueryTimeoutError):
            executor.execute_query('SELECT x FROM t', timeout=5)
        self.assertIn(('rollback',), conn.log)
        self.assertNotIn(('commit',), conn.log)
        self.assertTrue(conn.autocommit)
        self.assertEqual(self.plain_queries(conn), [])

    def test_cursor_names_are_unique_per_call(self):
        executor = PostgreSQLExecutor('fake-host', 5432)
        executor._connection = conn = _FakePgConnection(named_result=(['x'], [(1,)]))
        executor.execute_query('SELECT 1')
        executor.execute_query('SELECT 1')
        self.assertNotEqual(conn.named[0].name, conn.named[1].name)


class _FakeMyCursor:
    """PyMySQL buffered cursor."""

    def __init__(self, conn):
        self.conn = conn
        self.description = None
        self.rowcount = -1
        self._rows = []

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, query, params=None):
        self.conn.log.append(('buffered', query))
        if query.startswith('SET '):
            return
        result = self.conn.result
        if result is None:
            self.rowcount = self.conn.rowcount
        else:
            self.description = [(c,) for c in result[0]]
            self._rows = list(result[1])

    def fetchmany(self, size):
        rows, self._rows = self._rows[:size], self._rows[size:]
        return rows


class _FakeSSCursor:
    """PyMySQL unbuffered cursor: close() drains whatever is left on the wire."""

    def __init__(self, conn):
        self.conn = conn
        self.description = None
        self.rowcount = -1
        self.closed = False
        self.fetch_sizes = []

    def execute(self, query, params=None):
        self.conn.log.append(('unbuffered', query))
        result = self.conn.result
        if result is None:
            self.rowcount = self.conn.rowcount
        else:
            self.description = [(c,) for c in result[0]]

    def fetchmany(self, size):
        self.fetch_sizes.append(size)
        return list(self.conn.result[1][:size])

    def close(self):
        self.closed = True


class _FakeMyConnection:
    def __init__(self, result=None, rowcount=0):
        self.result = result
        self.rowcount = rowcount
        self.log = []
        self.unbuffered = []
        self.closed = False

    def cursor(self, cursor_class=None):
        if cursor_class is pymysql.cursors.SSCursor:
            cur = _FakeSSCursor(self)
            self.unbuffered.append(cur)
            return cur
        return _FakeMyCursor(self)

    def close(self):
        self.closed = True


class MariadbStreamingTests(SimpleTestCase):
    def setUp(self):
        self.executor = MySQLExecutor('fake-host', 3306, database='g_isolated')
        self.fresh = _FakeMyConnection()
        patcher = mock.patch('sandbox.executors.mysql.pymysql.connect', return_value=self.fresh)
        self.connect = patcher.start()
        self.addCleanup(patcher.stop)

    def run_query(self, query, **conn_kwargs):
        self.executor._connection = conn = _FakeMyConnection(**conn_kwargs)
        return conn, self.executor.execute_query(query, timeout=5)

    def test_truncated_select_reconnects_instead_of_draining(self):
        conn, result = self.run_query('SELECT seq FROM seq_1_to_2500',
                                      result=(['seq'], _numbers(2500)))
        cur = conn.unbuffered[0]
        self.assertEqual(cur.fetch_sizes, [MAX_RESULT_ROWS + 1])
        self.assertFalse(cur.closed)
        self.assertTrue(conn.closed)
        self.connect.assert_called_once()
        self.assertEqual(self.connect.call_args.kwargs['database'], 'g_isolated')
        self.assertIs(self.executor._connection, self.fresh)
        self.assertTrue(result.success)
        self.assertEqual(result.columns, ['seq'])
        self.assertEqual(len(result.rows), MAX_RESULT_ROWS)
        self.assertEqual(result.row_count, MAX_RESULT_ROWS)
        self.assertTrue(result.truncated)

    def test_complete_select_closes_the_cursor_and_keeps_the_connection(self):
        conn, result = self.run_query('SELECT 1', result=(['1'], [(1,)]))
        self.assertTrue(conn.unbuffered[0].closed)
        self.assertFalse(conn.closed)
        self.connect.assert_not_called()
        self.assertIs(self.executor._connection, conn)
        self.assertEqual(result.rows, [[1]])
        self.assertFalse(result.truncated)

    def test_exactly_the_limit_is_not_truncated(self):
        conn, result = self.run_query('SELECT 1', result=(['x'], _numbers(MAX_RESULT_ROWS)))
        self.assertFalse(conn.closed)
        self.assertEqual(len(result.rows), MAX_RESULT_ROWS)
        self.assertFalse(result.truncated)

    def test_empty_select_keeps_columns(self):
        conn, result = self.run_query('SELECT a, b FROM t WHERE 0', result=(['a', 'b'], []))
        self.assertEqual(result.columns, ['a', 'b'])
        self.assertEqual(result.rows, [])
        self.assertFalse(conn.closed)

    def test_other_statements_keep_the_buffered_cursor(self):
        for query in ('UPDATE t SET x = 1', 'INSERT INTO t VALUES (1)', 'SHOW TABLES',
                      '# SELECT\nDELETE FROM t', 'SELECT 1; SELECT 2'):
            with self.subTest(query=query):
                conn, result = self.run_query(query, rowcount=2)
                self.assertEqual(conn.unbuffered, [])
                self.assertIn(('buffered', query), conn.log)
                self.assertEqual(result.affected_rows, 2)

    def test_failed_reconnect_still_returns_the_rows(self):
        self.connect.side_effect = pymysql.err.OperationalError(2003, "Can't connect")
        conn, result = self.run_query('SELECT x FROM t', result=(['x'], _numbers(1500)))
        self.assertTrue(result.success)
        self.assertTrue(result.truncated)
        self.assertIsNone(self.executor._connection)
