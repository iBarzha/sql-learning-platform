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


# Statements the fake plain cursor accepts without producing a result.
_PG_CONTROL = ('SET', 'SAVEPOINT', 'RELEASE', 'CLOSE', 'MOVE', 'BEGIN', 'COMMIT', 'ROLLBACK')


class _FakePgPlainCursor:
    """psycopg2 client-side cursor: everything arrives during execute().

    SQL-level cursors (DECLARE / FETCH) are served from the connection's named_result.
    """

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
        self.description = None
        self.rowcount = -1
        self._rows = []
        word = query.split(None, 1)[0].upper()
        if self.conn.fail_on is not None and self.conn.fail_on in query:
            raise psycopg2.errors.UndefinedTable('relation "missing" does not exist')
        if word in _PG_CONTROL:
            return
        if word == 'DECLARE':
            if self.conn.declare_error is not None:
                raise self.conn.declare_error
            return
        if word == 'FETCH':
            columns, rows = self.conn.named_result
            self.description = [(c,) for c in columns]
            self._rows = list(rows[:int(query.split()[2])])
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

    def fetchall(self):
        rows, self._rows = self._rows, []
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
                 declare_error=None, fetch_error=None, fail_on=None,
                 transaction_status=psycopg2.extensions.TRANSACTION_STATUS_IDLE):
        self.autocommit = True
        self.fail_on = fail_on
        self.closed = 0
        self.info = mock.Mock(transaction_status=transaction_status)
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

    def statements(self, conn):
        """Plain-cursor statements with generated cursor names replaced by "c"."""
        import re
        return [re.sub(r'"sandbox_fetch_[0-9a-f]+"', '"c"', e[1]) for e in conn.log
                if e[0] == 'plain' and not e[1].startswith('SET ')]

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
                      'SHOW search_path', "UPDATE t SET s = 'a;b'", '-- SELECT\nDELETE FROM t'):
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

    def test_select_in_user_transaction_streams_through_a_sql_cursor(self):
        _, conn, result = self.run_query(
            'SELECT x FROM t', named_result=(['x'], _numbers(2500)),
            transaction_status=psycopg2.extensions.TRANSACTION_STATUS_INTRANS)
        self.assertEqual(conn.named, [])
        self.assertEqual(self.statements(conn), [
            'SAVEPOINT sandbox_cursor',
            'DECLARE "c" NO SCROLL CURSOR FOR SELECT x FROM t',
            'FETCH FORWARD %d FROM "c"' % (MAX_RESULT_ROWS + 1),
            'CLOSE "c"',
            'RELEASE SAVEPOINT sandbox_cursor',
        ])
        self.assertNotIn(('commit',), conn.log)
        self.assertNotIn(('rollback',), conn.log)
        self.assertTrue(conn.autocommit)
        self.assertEqual(result.columns, ['x'])
        self.assertEqual(len(result.rows), MAX_RESULT_ROWS)
        self.assertEqual(result.row_count, MAX_RESULT_ROWS)
        self.assertTrue(result.truncated)

    def test_empty_select_in_user_transaction_keeps_columns(self):
        _, _, result = self.run_query('SELECT a, b FROM t WHERE false',
                                      named_result=(['a', 'b'], []),
                                      transaction_status=psycopg2.extensions.TRANSACTION_STATUS_INTRANS)
        self.assertEqual(result.columns, ['a', 'b'])
        self.assertEqual(result.rows, [])
        self.assertFalse(result.truncated)

    def test_rejected_declare_in_user_transaction_rolls_back_to_the_savepoint(self):
        _, conn, result = self.run_query(
            'SELECT 1 INTO t2', plain_rowcount=1, transaction_status=psycopg2.extensions.TRANSACTION_STATUS_INTRANS,
            declare_error=psycopg2.errors.SyntaxError('SELECT ... INTO is not allowed here'))
        self.assertEqual(self.statements(conn), [
            'SAVEPOINT sandbox_cursor',
            'DECLARE "c" NO SCROLL CURSOR FOR SELECT 1 INTO t2',
            'ROLLBACK TO SAVEPOINT sandbox_cursor',
            'RELEASE SAVEPOINT sandbox_cursor',
            'SELECT 1 INTO t2',
        ])
        self.assertNotIn(('commit',), conn.log)
        self.assertNotIn(('rollback',), conn.log)
        self.assertTrue(result.success)
        self.assertEqual(result.affected_rows, 1)

    def test_failed_transaction_keeps_the_plain_cursor(self):
        _, conn, _ = self.run_query(
            'SELECT x FROM t', plain_result=(['x'], [(1,)]),
            transaction_status=psycopg2.extensions.TRANSACTION_STATUS_INERROR)
        self.assertEqual(self.statements(conn), ['SELECT x FROM t'])
        self.assertEqual(conn.named, [])

    def test_script_runs_atomically_and_streams_the_last_statement(self):
        _, conn, result = self.run_query(
            "CREATE TABLE t (x int); INSERT INTO t VALUES (1); SELECT x FROM t",
            named_result=(['x'], _numbers(2500)))
        self.assertEqual(conn.named, [])
        self.assertEqual(self.statements(conn), [
            'BEGIN',
            'CREATE TABLE t (x int)',
            'INSERT INTO t VALUES (1)',
            'SAVEPOINT sandbox_cursor',
            'DECLARE "c" NO SCROLL CURSOR FOR SELECT x FROM t',
            'FETCH FORWARD %d FROM "c"' % (MAX_RESULT_ROWS + 1),
            'CLOSE "c"',
            'RELEASE SAVEPOINT sandbox_cursor',
            'COMMIT',
        ])
        self.assertEqual(result.columns, ['x'])
        self.assertEqual(len(result.rows), MAX_RESULT_ROWS)
        self.assertTrue(result.truncated)

    def test_failing_script_is_rolled_back_as_a_whole(self):
        _, conn, result = self.run_query(
            'INSERT INTO t VALUES (1); SELECT * FROM missing; SELECT 2',
            named_result=(['x'], [(1,)]), fail_on='missing')
        statements = self.statements(conn)
        self.assertEqual(statements[0], 'BEGIN')
        self.assertEqual(statements[-1], 'ROLLBACK')
        self.assertNotIn('COMMIT', statements)
        self.assertNotIn('SELECT 2', ' '.join(statements))
        self.assertFalse(result.success)
        self.assertIn('does not exist', result.error_message)

    def test_script_skips_earlier_results_on_the_server(self):
        _, conn, result = self.run_query('SELECT x FROM big; DELETE FROM t', plain_rowcount=3)
        self.assertEqual(self.statements(conn), [
            'BEGIN',
            'SAVEPOINT sandbox_cursor',
            'DECLARE "c" NO SCROLL CURSOR FOR SELECT x FROM big',
            'MOVE FORWARD ALL IN "c"',
            'CLOSE "c"',
            'RELEASE SAVEPOINT sandbox_cursor',
            'DELETE FROM t',
            'COMMIT',
        ])
        self.assertEqual(result.affected_rows, 3)
        self.assertEqual(result.columns, [])

    def test_script_in_user_transaction_runs_inside_it(self):
        _, conn, result = self.run_query('UPDATE t SET x = 1; SELECT x FROM t',
                                         named_result=(['x'], [(1,)]),
                                         transaction_status=psycopg2.extensions.TRANSACTION_STATUS_INTRANS)
        self.assertEqual(self.statements(conn), [
            'UPDATE t SET x = 1',
            'SAVEPOINT sandbox_cursor',
            'DECLARE "c" NO SCROLL CURSOR FOR SELECT x FROM t',
            'FETCH FORWARD %d FROM "c"' % (MAX_RESULT_ROWS + 1),
            'CLOSE "c"',
            'RELEASE SAVEPOINT sandbox_cursor',
        ])
        self.assertEqual(result.rows, [[1]])

    def test_scripts_kept_whole(self):
        for query in ('BEGIN; SELECT 1', 'SELECT 1; COMMIT', 'INSERT INTO t VALUES (1); END',
                      'SELECT 1 /* a /* b */ ; */; SELECT 2', 'SELECT a$b FROM t; SELECT 2'):
            with self.subTest(query=query):
                _, conn, _ = self.run_query(query, plain_rowcount=1)
                self.assertEqual(self.statements(conn), [query])

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
        if self.conn.execute_error is not None:
            raise self.conn.execute_error
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
    def __init__(self, result=None, rowcount=0, server_status=0, execute_error=None):
        self.result = result
        self.rowcount = rowcount
        self.server_status = server_status
        self.execute_error = execute_error
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

    def test_user_transaction_caps_on_the_server_without_reconnecting(self):
        in_trans = pymysql.constants.SERVER_STATUS.SERVER_STATUS_IN_TRANS
        conn, result = self.run_query('SELECT x FROM t', result=(['x'], _numbers(1500)),
                                      server_status=in_trans)
        statements = [e[1] for e in conn.log if not e[1].startswith('SET max_')]
        self.assertEqual(statements, ['SET SESSION sql_select_limit = %s', 'SELECT x FROM t',
                                      'SET SESSION sql_select_limit = DEFAULT'])
        self.assertEqual(conn.log[1][0], 'buffered')
        self.assertEqual(len(conn.unbuffered), 1)
        self.assertTrue(conn.unbuffered[0].closed)   # drained, the transaction stays
        self.assertFalse(conn.closed)
        self.connect.assert_not_called()
        self.assertEqual(len(result.rows), MAX_RESULT_ROWS)
        self.assertTrue(result.truncated)

    def test_select_limit_is_reset_when_the_query_fails(self):
        in_trans = pymysql.constants.SERVER_STATUS.SERVER_STATUS_IN_TRANS
        conn, result = self.run_query(
            'SELECT x FROM missing', server_status=in_trans,
            execute_error=pymysql.err.OperationalError(1146, "Table 'missing' doesn't exist"))
        self.assertEqual(conn.log[-1], ('buffered', 'SET SESSION sql_select_limit = DEFAULT'))
        self.assertFalse(result.success)
        self.connect.assert_not_called()

    def test_outside_a_transaction_the_select_limit_is_not_touched(self):
        conn, _ = self.run_query('SELECT 1', result=(['1'], [(1,)]))
        self.assertFalse(any('sql_select_limit' in e[1] for e in conn.log))

    def test_row_query_without_a_result_set_reports_affected_rows(self):
        conn, result = self.run_query('SELECT 1 INTO @v', rowcount=1)
        self.assertEqual(len(conn.unbuffered), 1)
        self.assertTrue(conn.unbuffered[0].closed)
        self.assertEqual(conn.unbuffered[0].fetch_sizes, [])
        self.assertTrue(result.success)
        self.assertEqual(result.affected_rows, 1)
        self.assertEqual(result.columns, [])

    def test_failed_execute_closes_the_cursor_and_maps_the_error(self):
        conn, result = self.run_query(
            'SELECT x FROM missing',
            execute_error=pymysql.err.OperationalError(1146, "Table 'missing' doesn't exist"))
        self.assertTrue(conn.unbuffered[0].closed)
        self.assertFalse(result.success)
        self.assertEqual(result.error_message, "Table 'missing' doesn't exist")

    def test_failed_reconnect_still_returns_the_rows(self):
        self.connect.side_effect = pymysql.err.OperationalError(2003, "Can't connect")
        conn, result = self.run_query('SELECT x FROM t', result=(['x'], _numbers(1500)))
        self.assertTrue(result.success)
        self.assertTrue(result.truncated)
        self.assertIsNone(self.executor._connection)


class SplitStatementsTests(SimpleTestCase):
    def split(self, query):
        from sandbox.executors.postgresql import _split_statements
        return _split_statements(query)

    def test_splits_at_top_level_semicolons_only(self):
        cases = {
            'SELECT 1': ['SELECT 1'],
            'SELECT 1; SELECT 2;': ['SELECT 1', 'SELECT 2'],
            "SELECT 'a;b'; SELECT 2": ["SELECT 'a;b'", 'SELECT 2'],
            "SELECT 'it''s;'; SELECT 2": ["SELECT 'it''s;'", 'SELECT 2'],
            "SELECT E'x\\';y'; SELECT 2": ["SELECT E'x\\';y'", 'SELECT 2'],
            'SELECT "a;b" FROM t; SELECT 2': ['SELECT "a;b" FROM t', 'SELECT 2'],
            'SELECT $$a;b$$; SELECT 2': ['SELECT $$a;b$$', 'SELECT 2'],
            'SELECT $t$x;$$y$t$; SELECT 2': ['SELECT $t$x;$$y$t$', 'SELECT 2'],
            'SELECT 1 -- c;\n; SELECT 2': ['SELECT 1 -- c;', 'SELECT 2'],
            'SELECT /* ; */ 1; SELECT 2': ['SELECT /* ; */ 1', 'SELECT 2'],
        }
        for query, expected in cases.items():
            with self.subTest(query=query):
                self.assertEqual(self.split(query), expected)

    def test_drops_empty_and_comment_only_pieces(self):
        self.assertEqual(self.split('SELECT 1; -- done\n;;'), ['SELECT 1'])
        self.assertEqual(self.split(';;'), [])

    def test_untrusted_tokenization_is_refused(self):
        for query in ('SELECT 1 /* a /* b */ ; */; SELECT 2',   # nested comment
                      'SELECT a$b FROM t; SELECT 2',             # $ in a bare identifier
                      "SELECT 'open; SELECT 2"):                 # unclosed literal
            with self.subTest(query=query):
                self.assertIsNone(self.split(query))
