"""Grading through the real sandbox executors, one engine at a time.

These need the sandbox containers published on localhost:

    docker compose -f docker-compose.yml -f docker-compose.dev-ports.yml up -d \
        sandbox-postgres sandbox-mariadb sandbox-mongodb sandbox-redis
    SANDBOX_INTEGRATION=1 SANDBOX_POSTGRESQL_HOST=127.0.0.1 SANDBOX_POSTGRESQL_PORT=55432 \
    SANDBOX_MARIADB_HOST=127.0.0.1 SANDBOX_MARIADB_PORT=53306 \
    SANDBOX_MONGODB_HOST=127.0.0.1 SANDBOX_MONGODB_PORT=57017 \
    SANDBOX_REDIS_HOST=127.0.0.1 SANDBOX_REDIS_PORT=56379 \
    python manage.py test sandbox.test_grading_engines --settings=config.settings_test

Without SANDBOX_INTEGRATION=1 every engine test except SQLite is skipped.
"""

import os
import socket
import unittest
from decimal import Decimal

from django.test import TestCase

from grading.runner import build_task, make_runner, make_sequence_runner
from grading.service import CheckDataset, grade
from sandbox.pool import SANDBOX_DATABASES

INTEGRATION = os.getenv('SANDBOX_INTEGRATION') == '1'


def reachable(db_type: str) -> bool:
    if db_type == 'sqlite':
        return True
    if not INTEGRATION:
        return False
    cfg = SANDBOX_DATABASES[db_type]
    try:
        with socket.create_connection((cfg.host, cfg.port), timeout=2):
            return True
    except OSError:
        return False


class FakeDataset:
    def __init__(self, schema_sql, seed_sql):
        self.schema_sql = schema_sql
        self.seed_sql = seed_sql


SQL_SCHEMA = """
CREATE TABLE departments (id INTEGER PRIMARY KEY, name VARCHAR(100));
CREATE TABLE employees (
    id INTEGER PRIMARY KEY, name VARCHAR(100), dept_id INTEGER,
    salary NUMERIC(10,2), bonus NUMERIC(10,2)
);
"""
SQL_DEPTS = "INSERT INTO departments VALUES (1,'Розробка'),(2,'Аналітика'),(3,'Підтримка');"
SQL_EMPS = """
INSERT INTO employees VALUES
 (1,'Іваненко',1,6000,500),(2,'Петренко',1,4000,300),(3,'Коваленко',2,7000,800),
 (4,'Шевченко',3,3000,200),(5,'Бондаренко',2,5500,400);
"""
SQL_SEED = SQL_DEPTS + SQL_EMPS
SQL_EMPTY_DEPT = SQL_DEPTS + "INSERT INTO departments VALUES (4,'Кадри');" + SQL_EMPS
SQL_BOUNDARY = SQL_SEED + "INSERT INTO employees VALUES (8,'Ткаченко',1,5000,150);"
SQL_DUPLICATES = SQL_SEED + "INSERT INTO employees VALUES (6,'Іваненко',2,4500,100);"
SQL_NULLS = SQL_SEED + "INSERT INTO employees VALUES (7,'Мельник',3,3200,NULL);"

COUNT_PER_DEPT = ("SELECT d.name, COUNT(e.id) FROM departments d "
                  "LEFT JOIN employees e ON e.dept_id = d.id GROUP BY d.name")


class SqlEngineMixin:
    """Shared grading scenarios; subclasses set db_type and any dialect quirks."""

    db_type = ''

    @classmethod
    def setUpClass(cls):
        # Decide before Django opens its per-class transaction, so a skip leaves nothing behind.
        if not reachable(cls.db_type):
            raise unittest.SkipTest(f'{cls.db_type} sandbox is not reachable')
        super().setUpClass()

    def grade(self, student, reference, *, hidden=(), **kwargs):
        task = build_task(
            self.db_type,
            reference_query=reference,
            dataset=FakeDataset(SQL_SCHEMA, SQL_SEED),
            check_datasets=[{'name': n, 'seed_sql': s, 'targets': n} for n, s in hidden],
            **kwargs,
        )
        return grade(task, student, make_runner(self.db_type, 10))

    def test_correct_answer_with_aliases(self):
        r = self.grade(
            "SELECT dep.name AS x, COUNT(emp.id) AS y FROM departments dep "
            "LEFT JOIN employees emp ON emp.dept_id = dep.id GROUP BY dep.name",
            COUNT_PER_DEPT, hidden=[('порожній відділ', SQL_EMPTY_DEPT)])
        self.assertTrue(r.passed, r.feedback)
        self.assertEqual(r.score, Decimal('100.00'))

    def test_inner_join_caught_by_hidden_dataset(self):
        r = self.grade(
            "SELECT d.name, COUNT(e.id) FROM departments d "
            "JOIN employees e ON e.dept_id = d.id GROUP BY d.name",
            COUNT_PER_DEPT, hidden=[('порожній відділ', SQL_EMPTY_DEPT)])
        self.assertFalse(r.passed)
        self.assertEqual(r.feedback['failed_datasets'][0]['name'], 'порожній відділ')

    def test_boundary_operator(self):
        ref = 'SELECT name FROM employees WHERE salary >= 5000'
        ok = self.grade(ref, ref, hidden=[('межа', SQL_BOUNDARY)])
        bad = self.grade('SELECT name FROM employees WHERE salary > 5000', ref,
                         hidden=[('межа', SQL_BOUNDARY)])
        self.assertTrue(ok.passed, ok.feedback)
        self.assertFalse(bad.passed)

    def test_duplicates_are_significant(self):
        ref = 'SELECT name FROM employees'
        self.assertTrue(self.grade(ref, ref, hidden=[('однофамільці', SQL_DUPLICATES)]).passed)
        self.assertFalse(self.grade('SELECT DISTINCT name FROM employees', ref,
                                    hidden=[('однофамільці', SQL_DUPLICATES)]).passed)

    def test_null_is_not_zero(self):
        ref = 'SELECT bonus FROM employees'
        self.assertTrue(self.grade(ref, ref, hidden=[('NULL', SQL_NULLS)]).passed)
        self.assertFalse(self.grade('SELECT COALESCE(bonus, 0) FROM employees', ref,
                                    hidden=[('NULL', SQL_NULLS)]).passed)

    def test_decimal_aggregate_matches(self):
        ref = 'SELECT SUM(salary) FROM employees'
        r = self.grade('SELECT SUM(salary) AS total FROM employees', ref)
        self.assertTrue(r.passed, r.feedback)

    def test_hardcode_scores_zero(self):
        r = self.grade("SELECT 'Розробка', 2 UNION ALL SELECT 'Аналітика', 2 "
                       "UNION ALL SELECT 'Підтримка', 1", COUNT_PER_DEPT)
        self.assertEqual(r.score, Decimal('0.00'))

    def test_union_is_allowed_and_graded(self):
        ref = 'SELECT name FROM departments UNION SELECT name FROM employees'
        r = self.grade(ref, ref)
        self.assertTrue(r.passed, r.feedback)

    def test_literal_with_grant_is_not_blocked(self):
        ref = "SELECT name FROM employees WHERE name = 'Grant'"
        r = self.grade(ref, ref)
        self.assertTrue(r.execution.success, r.feedback)

    def test_wrong_column_type_is_wrong(self):
        r = self.grade('SELECT name FROM employees', 'SELECT salary FROM employees')
        self.assertFalse(r.passed)

    def test_ordering_from_reference(self):
        ref = 'SELECT name FROM employees ORDER BY salary DESC'
        self.assertTrue(self.grade(ref, ref).passed)
        self.assertFalse(self.grade('SELECT name FROM employees ORDER BY salary ASC', ref).passed)

    def test_syntax_error_is_reported(self):
        r = self.grade('SELEC name FROM employees', 'SELECT name FROM employees')
        self.assertFalse(r.execution.success)
        self.assertEqual(r.score, Decimal('0.00'))

    def grade_dml(self, student, reference):
        task = build_task(self.db_type, reference_query=reference,
                          dataset=FakeDataset(SQL_SCHEMA, SQL_SEED), check_datasets=[])
        return grade(task, student, make_runner(self.db_type, 10),
                     run_sequence=make_sequence_runner(self.db_type, 10))

    def test_update_is_graded_by_table_state(self):
        ref = 'UPDATE employees SET salary = salary + 100 WHERE dept_id = 1'
        self.assertTrue(self.grade_dml(ref, ref).passed)
        self.assertFalse(self.grade_dml('UPDATE employees SET salary = salary + 100', ref).passed)
        self.assertFalse(self.grade_dml('DELETE FROM employees WHERE dept_id = 1', ref).passed)

    def test_insert_is_graded_by_table_state(self):
        ref = "INSERT INTO departments VALUES (4, 'Кадри')"
        self.assertTrue(self.grade_dml("INSERT INTO departments (id, name) VALUES (4, 'Кадри')", ref).passed)
        self.assertFalse(self.grade_dml("INSERT INTO departments VALUES (4, 'Маркетинг')", ref).passed)


    def test_concurrent_executions_do_not_disturb_each_other(self):
        """Twelve gradings at once: every one must see its own freshly seeded tables."""
        from concurrent.futures import ThreadPoolExecutor

        from sandbox.pool import get_sandbox_pool

        pool = get_sandbox_pool()

        def one(i):
            seed = SQL_DEPTS + SQL_EMPS if i % 2 else SQL_EMPTY_DEPT
            result = pool.execute_query(self.db_type, COUNT_PER_DEPT, SQL_SCHEMA, seed, timeout=10)
            return result.success, len(result.rows), result.error_message

        with ThreadPoolExecutor(max_workers=12) as ex:
            outcomes = list(ex.map(one, range(12)))

        for i, (ok, rows, err) in enumerate(outcomes):
            self.assertTrue(ok, err)
            self.assertEqual(rows, 3 if i % 2 else 4)

    def test_numeric_and_date_columns_are_stored(self):
        """NUMERIC values come back as Decimal; storing them used to be HTTP 500."""
        import json
        from submissions.storage import json_safe
        ref = 'SELECT name, salary FROM employees WHERE salary > 5000'
        r = self.grade(ref, ref)
        self.assertTrue(r.passed, r.feedback)
        json.dumps(json_safe(r.execution.rows))   # must not raise on Decimal


class SqliteEngineTests(SqlEngineMixin, TestCase):
    db_type = 'sqlite'


SERIES_2500 = ('WITH RECURSIVE n(x) AS (SELECT 1 UNION ALL SELECT x + 1 FROM n WHERE x < 2500) '
               'SELECT x FROM n')


class StreamingMixin:
    """Server-side streaming: only MAX_RESULT_ROWS + 1 rows may leave the sandbox.

    Subclasses set `huge_cross_join`, a result far too large to compute or transfer
    in full; it must come back capped and fast because only the fetched rows are produced.
    """

    huge_cross_join = ''

    def run_one(self, query, timeout=10):
        from sandbox.pool import get_sandbox_pool
        return get_sandbox_pool().execute_query(self.db_type, query, SQL_SCHEMA, SQL_SEED,
                                                timeout=timeout)

    def run_sequence(self, queries):
        from sandbox.pool import get_sandbox_pool
        return get_sandbox_pool().execute_sequence(self.db_type, queries, SQL_SCHEMA, SQL_SEED,
                                                   timeout=10)

    def test_large_result_is_capped(self):
        from sandbox.executors.base import MAX_RESULT_ROWS
        r = self.run_one(SERIES_2500)
        self.assertTrue(r.success, r.error_message)
        self.assertEqual(r.columns, ['x'])
        self.assertEqual(len(r.rows), MAX_RESULT_ROWS)
        self.assertEqual(r.row_count, MAX_RESULT_ROWS)
        self.assertEqual([row[0] for row in r.rows[:3]], [1, 2, 3])
        self.assertTrue(r.truncated)

    def test_huge_result_is_not_computed_in_full(self):
        import time
        from sandbox.executors.base import MAX_RESULT_ROWS
        start = time.monotonic()
        r = self.run_one(self.huge_cross_join, timeout=5)
        self.assertTrue(r.success, r.error_message)
        self.assertEqual(len(r.rows), MAX_RESULT_ROWS)
        self.assertTrue(r.truncated)
        self.assertLess(time.monotonic() - start, 5)

    def test_empty_select_keeps_columns(self):
        r = self.run_one('SELECT id, name FROM employees WHERE id < 0')
        self.assertTrue(r.success, r.error_message)
        self.assertEqual(r.columns, ['id', 'name'])
        self.assertEqual(r.rows, [])
        self.assertEqual(r.row_count, 0)
        self.assertFalse(r.truncated)

    def test_dml_reports_affected_rows(self):
        results = self.run_sequence([
            'UPDATE employees SET salary = salary + 1000 WHERE dept_id = 1',
            'SELECT COUNT(*) FROM employees WHERE salary > 5500',
        ])
        self.assertTrue(all(r.success for r in results), [r.error_message for r in results])
        self.assertEqual(results[0].affected_rows, 2)
        self.assertEqual(results[0].columns, [])
        self.assertEqual(results[1].rows, [[2]])

    def test_connection_is_usable_after_a_truncated_result(self):
        results = self.run_sequence([
            'CREATE TABLE notes (id INTEGER)',
            SERIES_2500,
            'INSERT INTO notes VALUES (1)',
            'SELECT COUNT(*) FROM notes',
        ])
        self.assertEqual(len(results), 4, [r.error_message for r in results])
        self.assertTrue(all(r.success for r in results), [r.error_message for r in results])
        self.assertTrue(results[1].truncated)
        self.assertEqual(results[3].rows, [[1]])

    def test_user_transaction_rollback_survives_a_select(self):
        results = self.run_sequence([
            'BEGIN',
            'UPDATE employees SET salary = 0',
            'SELECT name, salary FROM employees',
            'ROLLBACK',
            'SELECT COUNT(*) FROM employees WHERE salary = 0',
        ])
        self.assertEqual(len(results), 5, [r.error_message for r in results])
        self.assertTrue(all(r.success for r in results), [r.error_message for r in results])
        self.assertEqual(results[4].rows, [[0]])

    def test_user_transaction_survives_a_truncated_select(self):
        results = self.run_sequence([
            'BEGIN',
            'UPDATE employees SET salary = 0',
            SERIES_2500,
            'COMMIT',
            'SELECT COUNT(*) FROM employees WHERE salary = 0',
        ])
        self.assertEqual(len(results), 5, [r.error_message for r in results])
        self.assertTrue(all(r.success for r in results), [r.error_message for r in results])
        self.assertTrue(results[2].truncated)
        self.assertEqual(results[4].rows, [[5]])

    def on_one_connection(self, queries):
        """Run every statement on one seeded connection, failures included."""
        from sandbox.exceptions import QuerySyntaxError, QueryTimeoutError
        from sandbox.executors.base import QueryResult
        from sandbox.pool import get_sandbox_pool
        results = []
        with get_sandbox_pool()._isolated(self.db_type, SQL_SCHEMA, SQL_SEED) as executor:
            for query in queries:
                try:
                    results.append(executor.execute_query(query, timeout=10))
                except (QuerySyntaxError, QueryTimeoutError) as e:
                    results.append(QueryResult(success=False, error_message=str(e)))
        return results

    def test_select_in_user_transaction_is_capped_and_the_transaction_survives(self):
        from sandbox.executors.base import MAX_RESULT_ROWS
        results = self.on_one_connection([
            'BEGIN',
            'UPDATE employees SET salary = 0',
            SERIES_2500,
            'SELECT COUNT(*) FROM employees WHERE salary = 0',
            'ROLLBACK',
            'SELECT COUNT(*) FROM employees WHERE salary = 0',
            SERIES_2500,
        ])
        self.assertTrue(all(r.success for r in results), [r.error_message for r in results])
        self.assertEqual(len(results[2].rows), MAX_RESULT_ROWS)
        self.assertTrue(results[2].truncated)
        self.assertEqual(results[3].rows, [[5]])
        self.assertEqual(results[5].rows, [[0]])
        # Outside the transaction again nothing of the in-transaction cap lingers.
        self.assertEqual(len(results[6].rows), MAX_RESULT_ROWS)
        self.assertTrue(results[6].truncated)

    def test_huge_select_in_user_transaction_is_not_computed_in_full(self):
        from sandbox.executors.base import MAX_RESULT_ROWS
        results = self.on_one_connection(['BEGIN', self.huge_cross_join, 'SELECT 1', 'ROLLBACK'])
        self.assertTrue(all(r.success for r in results), [r.error_message for r in results])
        self.assertEqual(len(results[1].rows), MAX_RESULT_ROWS)
        self.assertTrue(results[1].truncated)

    def test_undeclarable_select_in_user_transaction_keeps_the_transaction(self):
        results = self.on_one_connection([
            'BEGIN',
            'UPDATE employees SET salary = 0',
            self.select_into,
            self.read_back,
            'SELECT COUNT(*) FROM employees WHERE salary = 0',
            'ROLLBACK',
            'SELECT COUNT(*) FROM employees WHERE salary = 0',
        ])
        self.assertTrue(all(r.success for r in results), [r.error_message for r in results])
        self.assertEqual(results[3].rows, [[5]])
        self.assertEqual(results[4].rows, [[5]])
        self.assertEqual(results[6].rows, [[0]])

    def test_syntax_error_still_fails(self):
        r = self.run_one('SELECT FROM WHERE')
        self.assertFalse(r.success)
        self.assertTrue(r.error_message)


class PostgresEngineTests(StreamingMixin, SqlEngineMixin, TestCase):
    db_type = 'postgresql'
    select_into = 'SELECT * INTO emp_copy FROM employees'
    read_back = 'SELECT COUNT(*) FROM emp_copy'
    huge_cross_join = ('SELECT a.x FROM generate_series(1, 3000) a(x) '
                       'CROSS JOIN generate_series(1, 3000) b CROSS JOIN generate_series(1, 3000) c')

    def test_parenthesised_statement_list_stays_one_statement(self):
        results = self.on_one_connection([
            'CREATE TABLE audit (id INTEGER); CREATE TABLE audit2 (id INTEGER)',
            'CREATE RULE log_dept AS ON INSERT TO departments DO ALSO '
            '(INSERT INTO audit VALUES (NEW.id); INSERT INTO audit2 VALUES (NEW.id))',
            "INSERT INTO departments VALUES (9, 'x')",
            'SELECT (SELECT COUNT(*) FROM audit), (SELECT COUNT(*) FROM audit2)',
        ])
        self.assertTrue(all(r.success for r in results), [r.error_message for r in results])
        self.assertEqual(results[3].rows, [[1, 1]])

    def test_script_splits_around_a_parenthesised_statement_list(self):
        from sandbox.executors.base import MAX_RESULT_ROWS
        results = self.on_one_connection([
            'CREATE TABLE audit (id INTEGER); CREATE TABLE audit2 (id INTEGER); '
            'CREATE RULE log_dept AS ON INSERT TO departments DO ALSO '
            '(INSERT INTO audit VALUES (NEW.id); INSERT INTO audit2 VALUES (NEW.id)); '
            "INSERT INTO departments VALUES (9, 'x'); " + SERIES_2500,
            'SELECT (SELECT COUNT(*) FROM audit), (SELECT COUNT(*) FROM audit2)',
        ])
        self.assertTrue(all(r.success for r in results), [r.error_message for r in results])
        self.assertEqual(len(results[0].rows), MAX_RESULT_ROWS)
        self.assertTrue(results[0].truncated)
        self.assertEqual(results[1].rows, [[1, 1]])

    def test_identifier_with_dollar_signs_splits_the_script(self):
        results = self.on_one_connection([
            'CREATE TABLE a$b$c (x$b$y INTEGER); INSERT INTO a$b$c VALUES (7); '
            'SELECT x$b$y FROM a$b$c',
        ])
        self.assertTrue(results[0].success, results[0].error_message)
        self.assertEqual(results[0].rows, [[7]])

    def test_script_returns_the_last_result(self):
        r = self.run_one('CREATE TEMP TABLE tt AS SELECT id FROM employees; '
                         "INSERT INTO tt VALUES (99); SELECT COUNT(*) AS n FROM tt")
        self.assertTrue(r.success, r.error_message)
        self.assertEqual(r.columns, ['n'])
        self.assertEqual(r.rows, [[6]])

    def test_failing_script_leaves_no_trace(self):
        results = self.on_one_connection([
            "INSERT INTO departments VALUES (9, 'x'); SELECT * FROM missing_table; SELECT 1",
            'SELECT COUNT(*) FROM departments',
        ])
        self.assertFalse(results[0].success)
        self.assertEqual(results[1].rows, [[3]])

    def test_script_with_a_large_last_select_is_capped(self):
        from sandbox.executors.base import MAX_RESULT_ROWS
        r = self.run_one("UPDATE employees SET bonus = 0; " + SERIES_2500 + ';')
        self.assertTrue(r.success, r.error_message)
        self.assertEqual(r.columns, ['x'])
        self.assertEqual(len(r.rows), MAX_RESULT_ROWS)
        self.assertTrue(r.truncated)

    def test_script_with_a_huge_last_select_is_not_computed_in_full(self):
        from sandbox.executors.base import MAX_RESULT_ROWS
        r = self.run_one('SELECT 1; ' + self.huge_cross_join, timeout=5)
        self.assertTrue(r.success, r.error_message)
        self.assertEqual(len(r.rows), MAX_RESULT_ROWS)
        self.assertTrue(r.truncated)

    def test_script_inside_user_transaction(self):
        results = self.on_one_connection([
            'BEGIN',
            "UPDATE employees SET salary = 0; SELECT COUNT(*) FROM employees WHERE salary = 0",
            'ROLLBACK',
            'SELECT COUNT(*) FROM employees WHERE salary = 0',
        ])
        self.assertTrue(all(r.success for r in results), [r.error_message for r in results])
        self.assertEqual(results[1].rows, [[5]])
        self.assertEqual(results[3].rows, [[0]])

    def test_script_with_its_own_transaction_is_capped_and_committed(self):
        from sandbox.executors.base import MAX_RESULT_ROWS
        results = self.on_one_connection([
            'BEGIN; UPDATE employees SET salary = 0; ' + SERIES_2500 + '; COMMIT; ' + SERIES_2500,
            'SELECT COUNT(*) FROM employees WHERE salary = 0',
        ])
        self.assertTrue(all(r.success for r in results), [r.error_message for r in results])
        self.assertEqual(len(results[0].rows), MAX_RESULT_ROWS)
        self.assertTrue(results[0].truncated)
        self.assertEqual(results[1].rows, [[5]])

    def test_select_after_begin_in_a_script_is_capped(self):
        from sandbox.executors.base import MAX_RESULT_ROWS
        results = self.on_one_connection([
            'BEGIN; ' + SERIES_2500,
            'COMMIT',
            'SELECT 1',
        ])
        self.assertTrue(all(r.success for r in results), [r.error_message for r in results])
        self.assertEqual(results[0].columns, ['x'])
        self.assertEqual(len(results[0].rows), MAX_RESULT_ROWS)
        self.assertTrue(results[0].truncated)

    def test_huge_select_after_begin_in_a_script_is_not_computed_in_full(self):
        import time
        from sandbox.executors.base import MAX_RESULT_ROWS
        start = time.monotonic()
        results = self.on_one_connection(['BEGIN; ' + self.huge_cross_join + '; COMMIT; '
                                          + self.huge_cross_join])
        self.assertTrue(results[0].success, results[0].error_message)
        self.assertEqual(len(results[0].rows), MAX_RESULT_ROWS)
        self.assertLess(time.monotonic() - start, 9)

    def test_failing_script_with_its_own_transaction_stops_at_the_error(self):
        results = self.on_one_connection([
            'BEGIN; UPDATE employees SET salary = 0; SELECT 1/0; ROLLBACK',
            'ROLLBACK',
            'SELECT COUNT(*) FROM employees WHERE salary = 0',
            'SELECT 1',
        ])
        self.assertFalse(results[0].success)
        self.assertIn('division by zero', results[0].error_message)
        # The transaction is left failed, as the user's statements left it; the user's
        # next ROLLBACK ends it, the update is undone and the connection works.
        self.assertTrue(all(r.success for r in results[1:]), [r.error_message for r in results])
        self.assertEqual(results[2].rows, [[0]])
        self.assertEqual(results[3].rows, [[1]])

    def test_select_into_falls_back_to_a_plain_statement(self):
        results = self.run_sequence(['SELECT * INTO emp_copy FROM employees',
                                     'SELECT COUNT(*) FROM emp_copy'])
        self.assertTrue(all(r.success for r in results), [r.error_message for r in results])
        self.assertEqual(results[1].rows, [[5]])

    def test_data_modifying_with_falls_back_to_a_plain_statement(self):
        results = self.run_sequence([
            'WITH gone AS (DELETE FROM employees WHERE dept_id = 1 RETURNING id) '
            'SELECT COUNT(*) FROM gone',
            'SELECT COUNT(*) FROM employees',
        ])
        self.assertTrue(all(r.success for r in results), [r.error_message for r in results])
        self.assertEqual(results[0].rows, [[2]])
        self.assertEqual(results[1].rows, [[3]])

    def test_timeout_still_applies_to_streamed_queries(self):
        import time
        start = time.monotonic()
        r = self.run_one(self.huge_cross_join + ' ORDER BY 1 DESC', timeout=1)
        self.assertFalse(r.success)
        self.assertLess(time.monotonic() - start, 9)

    def test_truncated_result_is_still_graded_exactly(self):
        # 1500 rows exceed MAX_RESULT_ROWS; the verdict must come from EXCEPT ALL.
        ref = 'SELECT g FROM generate_series(1, 1500) AS g'
        self.assertTrue(self.grade(ref, ref).passed)
        almost = 'SELECT g FROM generate_series(1, 1500) AS g WHERE g <> 1400'
        self.assertFalse(self.grade(almost, ref).passed)


class MariadbEngineTests(StreamingMixin, SqlEngineMixin, TestCase):
    db_type = 'mariadb'
    huge_cross_join = 'SELECT a.seq FROM seq_1_to_3000 a, seq_1_to_3000 b, seq_1_to_3000 c'
    select_into = 'SELECT COUNT(*) INTO @n FROM employees'
    read_back = 'SELECT @n'

    def test_explicit_limit_in_user_transaction_is_capped(self):
        from sandbox.executors.base import MAX_RESULT_ROWS
        results = self.on_one_connection([
            'BEGIN',
            'UPDATE employees SET salary = 0',
            'SELECT seq FROM seq_1_to_5000 LIMIT 3000',
            'SELECT COUNT(*) FROM employees WHERE salary = 0',
            'ROLLBACK',
            'SELECT COUNT(*) FROM employees WHERE salary = 0',
        ])
        self.assertTrue(all(r.success for r in results), [r.error_message for r in results])
        self.assertEqual(len(results[2].rows), MAX_RESULT_ROWS)
        self.assertTrue(results[2].truncated)
        self.assertEqual(results[3].rows, [[5]])
        self.assertEqual(results[5].rows, [[0]])

    def test_truncated_result_is_still_graded_exactly(self):
        ref = 'SELECT seq FROM seq_1_to_1500'
        self.assertTrue(self.grade(ref, ref).passed)
        almost = 'SELECT seq FROM seq_1_to_1500 WHERE seq <> 1400'
        self.assertFalse(self.grade(almost, ref).passed)


MONGO_SEED = """
db.employees.insertMany([
  {"name": "Іваненко", "dept": "Розробка", "salary": 6000},
  {"name": "Петренко", "dept": "Розробка", "salary": 4000},
  {"name": "Коваленко", "dept": "Аналітика", "salary": 7000},
  {"name": "Шевченко", "dept": "Підтримка", "salary": 3000},
  {"name": "Бондаренко", "dept": "Аналітика", "salary": 5500}
]);
"""
MONGO_BOUNDARY = MONGO_SEED + 'db.employees.insertOne({"name": "Ткаченко", "dept": "Розробка", "salary": 5000});'


class MongoEngineTests(TestCase):
    db_type = 'mongodb'

    @classmethod
    def setUpClass(cls):
        if not reachable(cls.db_type):
            raise unittest.SkipTest('mongodb sandbox is not reachable')
        super().setUpClass()

    def grade(self, student, reference, *, hidden=()):
        task = build_task(
            self.db_type, reference_query=reference,
            dataset=FakeDataset('', MONGO_SEED),
            check_datasets=[{'name': n, 'seed_sql': s, 'targets': n} for n, s in hidden],
        )
        return grade(task, student, make_runner(self.db_type, 10))

    def test_same_query_passes_even_though_object_ids_differ_per_run(self):
        ref = 'db.employees.find({"salary": {"$gte": 5000}})'
        r = self.grade(ref, ref)
        self.assertTrue(r.passed, r.feedback)

    def test_projection_with_different_key_order_passes(self):
        ref = 'db.employees.find({"salary": {"$gte": 5000}}, {"_id": 0, "name": 1, "salary": 1})'
        student = 'db.employees.find({"salary": {"$gte": 5000}}, {"_id": 0, "salary": 1, "name": 1})'
        self.assertTrue(self.grade(student, ref).passed)

    def test_boundary_operator_caught_by_hidden_dataset(self):
        ref = 'db.employees.find({"salary": {"$gte": 5000}}, {"_id": 0, "name": 1})'
        student = 'db.employees.find({"salary": {"$gt": 5000}}, {"_id": 0, "name": 1})'
        self.assertTrue(self.grade(ref, ref, hidden=[('межа', MONGO_BOUNDARY)]).passed)
        self.assertFalse(self.grade(student, ref, hidden=[('межа', MONGO_BOUNDARY)]).passed)

    def test_wrong_filter_fails(self):
        ref = 'db.employees.find({"dept": "Розробка"}, {"_id": 0, "name": 1})'
        student = 'db.employees.find({"dept": "Аналітика"}, {"_id": 0, "name": 1})'
        r = self.grade(student, ref)
        self.assertFalse(r.passed)
        self.assertTrue(r.feedback['missing_rows'])

    def test_documents_are_shown_with_readable_unicode(self):
        # Displayed rows must contain the actual text, not \\u-escapes.
        result = make_runner(self.db_type, 10)(
            'db.employees.find({"dept": "Розробка"}, {"_id": 0, "name": 1})',
            CheckDataset('m', '', MONGO_SEED),
            'student',
        )
        self.assertTrue(result.success, result.error)
        self.assertIn('Іваненко', result.rows[0][0])
        self.assertNotIn('\\u0406', result.rows[0][0])


REDIS_SEED = """
SET counter 41
SADD tags red green blue
HSET user:1 name Іваненко age 30
"""


class RedisEngineTests(TestCase):
    db_type = 'redis'

    @classmethod
    def setUpClass(cls):
        if not reachable(cls.db_type):
            raise unittest.SkipTest('redis sandbox is not reachable')
        super().setUpClass()

    def grade(self, student, reference):
        task = build_task(self.db_type, reference_query=reference,
                          dataset=FakeDataset('', REDIS_SEED), check_datasets=[])
        return grade(task, student, make_runner(self.db_type, 10))

    def test_get_matches(self):
        self.assertTrue(self.grade('GET counter', 'GET counter').passed)

    def test_wrong_key_fails(self):
        r = self.grade('GET nope', 'GET counter')
        self.assertFalse(r.passed)

    def test_set_members_compare_regardless_of_order(self):
        self.assertTrue(self.grade('SMEMBERS tags', 'SMEMBERS tags').passed)

    def test_hash_matches(self):
        self.assertTrue(self.grade('HGETALL user:1', 'HGETALL user:1').passed)

    def test_blocked_command_is_an_execution_error(self):
        r = self.grade('FLUSHALL', 'GET counter')
        self.assertFalse(r.execution.success)
