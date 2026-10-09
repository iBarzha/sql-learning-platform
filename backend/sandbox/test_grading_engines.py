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


class PostgresEngineTests(SqlEngineMixin, TestCase):
    db_type = 'postgresql'

    def test_truncated_result_is_still_graded_exactly(self):
        # 1500 rows exceed MAX_RESULT_ROWS; the verdict must come from EXCEPT ALL.
        ref = 'SELECT g FROM generate_series(1, 1500) AS g'
        self.assertTrue(self.grade(ref, ref).passed)
        almost = 'SELECT g FROM generate_series(1, 1500) AS g WHERE g <> 1400'
        self.assertFalse(self.grade(almost, ref).passed)


class MariadbEngineTests(SqlEngineMixin, TestCase):
    db_type = 'mariadb'

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
