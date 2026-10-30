"""Row cap tests for the in-process SQLite executor.

PostgreSQL and MariaDB executors share the same fetchmany change but need
Docker sandboxes, so they are not exercised here.
"""
from django.test import SimpleTestCase

from sandbox.executors.base import MAX_RESULT_ROWS
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
