"""Unit tests for the grading service against a real in-memory SQLite database."""

import json
import sqlite3
import unittest
from decimal import Decimal

from grading.service import (
    CheckDataset,
    Execution,
    GradingTask,
    PURPOSE_DIFF,
    PURPOSE_REFERENCE,
    PURPOSE_STUDENT,
    grade,
)

SCHEMA = """
CREATE TABLE departments (id INTEGER PRIMARY KEY, name TEXT);
CREATE TABLE employees (
    id INTEGER PRIMARY KEY, name TEXT, dept_id INTEGER, salary REAL, bonus REAL
);
"""
DEPTS = "INSERT INTO departments VALUES (1,'Розробка'),(2,'Аналітика'),(3,'Підтримка');"
EMPS = """
INSERT INTO employees VALUES
 (1,'Іваненко',1,6000,500),(2,'Петренко',1,4000,300),(3,'Коваленко',2,7000,800),
 (4,'Шевченко',3,3000,200),(5,'Бондаренко',2,5500,400);
"""

PRIMARY = CheckDataset('основний', SCHEMA, DEPTS + EMPS)
EMPTY_DEPT = CheckDataset('порожній відділ', SCHEMA,
                          DEPTS + "INSERT INTO departments VALUES (4,'Кадри');" + EMPS,
                          targets='відділ без працівників')
DUPLICATES = CheckDataset('однофамільці', SCHEMA,
                          DEPTS + EMPS + "INSERT INTO employees VALUES (6,'Іваненко',2,4500,100);",
                          targets='два працівники з однаковим прізвищем')
BOUNDARY = CheckDataset('межа', SCHEMA,
                        DEPTS + EMPS + "INSERT INTO employees VALUES (8,'Ткаченко',1,5000,150);",
                        targets='зарплата рівно на межі')
NOBODY = CheckDataset('порожня вибірка', SCHEMA,
                      DEPTS + "INSERT INTO employees VALUES (1,'Іваненко',1,1000,10);",
                      targets='правильна відповідь порожня')

COUNT_PER_DEPT = ("SELECT d.name, COUNT(e.id) FROM departments d "
                  "LEFT JOIN employees e ON e.dept_id = d.id GROUP BY d.name")


def sqlite_runner(calls=None):
    def run(sql, dataset, purpose):
        if calls is not None:
            calls.append((purpose, sql))
        conn = sqlite3.connect(':memory:')
        try:
            conn.executescript(dataset.schema_sql)
            conn.executescript(dataset.seed_sql)
            cur = conn.execute(sql)
            columns = [d[0] for d in cur.description] if cur.description else []
            rows = [list(r) for r in cur.fetchall()]
            affected = cur.rowcount if cur.rowcount >= 0 else 0
            return Execution(True, columns, rows, affected_rows=affected)
        except sqlite3.Error as err:
            return Execution(False, error=str(err))
        finally:
            conn.close()
    return run


def sqlite_sequence_runner(calls=None):
    def run_sequence(sqls, dataset, purpose):
        if calls is not None:
            calls.append((purpose, list(sqls)))
        conn = sqlite3.connect(':memory:')
        results = []
        try:
            conn.executescript(dataset.schema_sql)
            conn.executescript(dataset.seed_sql)
            for sql in sqls:
                try:
                    cur = conn.execute(sql)
                    columns = [d[0] for d in cur.description] if cur.description else []
                    rows = [list(r) for r in cur.fetchall()]
                    affected = cur.rowcount if cur.rowcount >= 0 else 0
                    results.append(Execution(True, columns, rows, affected_rows=affected))
                except sqlite3.Error as err:
                    results.append(Execution(False, error=str(err)))
                    break
            return results
        finally:
            conn.close()
    return run_sequence


def task(reference, *, hidden=(), db_type='sqlite', **kwargs):
    return GradingTask(db_type=db_type, reference_query=reference, primary=PRIMARY,
                       hidden=list(hidden), **kwargs)


def score(result) -> Decimal:
    return result.score


def codes(result, passed=None):
    return {c['code'] for c in result.feedback['checks']
            if passed is None or c['passed'] == passed}


class CorrectAnswerTests(unittest.TestCase):
    def test_aliases_and_column_names_do_not_matter(self):
        student = ("SELECT dep.name AS відділ, COUNT(emp.id) AS n FROM departments dep "
                   "LEFT JOIN employees emp ON emp.dept_id = dep.id GROUP BY dep.name")
        r = grade(task(COUNT_PER_DEPT, hidden=[EMPTY_DEPT, NOBODY]), student, sqlite_runner())
        self.assertTrue(r.passed)
        self.assertEqual(score(r), Decimal('100.00'))
        self.assertTrue(r.feedback['result_match'])
        self.assertEqual(r.feedback['datasets_checked'], 3)

    def test_duplicate_rows_are_a_correct_answer(self):
        r = grade(task('SELECT name FROM employees', hidden=[DUPLICATES]),
                  'SELECT name FROM employees', sqlite_runner())
        self.assertTrue(r.passed)
        self.assertEqual(score(r), Decimal('100.00'))

    def test_subquery_instead_of_join_is_accepted(self):
        reference = ("SELECT e.name FROM employees e JOIN departments d ON d.id = e.dept_id "
                     "WHERE d.name = 'Розробка'")
        student = ("SELECT name FROM employees WHERE dept_id IN "
                   "(SELECT id FROM departments WHERE name = 'Розробка')")
        r = grade(task(reference, hidden=[EMPTY_DEPT, NOBODY]), student, sqlite_runner())
        self.assertTrue(r.passed)

    def test_between_and_explicit_range_are_equivalent(self):
        r = grade(task('SELECT name FROM employees WHERE salary BETWEEN 4000 AND 6000',
                       hidden=[BOUNDARY]),
                  'SELECT name FROM employees WHERE salary >= 4000 AND salary <= 6000',
                  sqlite_runner())
        self.assertTrue(r.passed)

    def test_execution_result_is_returned_for_display(self):
        r = grade(task('SELECT name FROM employees'), 'SELECT name FROM employees',
                  sqlite_runner())
        self.assertEqual(r.execution.columns, ['name'])
        self.assertEqual(len(r.execution.rows), 5)


class WrongAnswerTests(unittest.TestCase):
    def test_inner_join_is_caught_by_hidden_dataset(self):
        student = ("SELECT d.name, COUNT(e.id) FROM departments d "
                   "JOIN employees e ON e.dept_id = d.id GROUP BY d.name")
        r = grade(task(COUNT_PER_DEPT, hidden=[EMPTY_DEPT]), student, sqlite_runner())
        self.assertFalse(r.passed)
        self.assertEqual(score(r), Decimal('0.00'))
        self.assertEqual(r.feedback['passed_count'], r.feedback['total'] - 1)
        self.assertEqual(r.feedback['failed_datasets'][0]['name'], 'порожній відділ')
        self.assertTrue(any('відділ без працівників' in h for h in r.feedback['hints']))

    def test_all_failing_hidden_datasets_are_reported(self):
        r = grade(task('SELECT name FROM employees WHERE salary >= 5000',
                       hidden=[BOUNDARY, NOBODY, EMPTY_DEPT]),
                  'SELECT name FROM employees WHERE salary > 5000', sqlite_runner())
        names = [d['name'] for d in r.feedback['failed_datasets']]
        self.assertEqual(names, ['межа'])

    def test_extra_distinct_is_caught(self):
        r = grade(task('SELECT name FROM employees', hidden=[DUPLICATES]),
                  'SELECT DISTINCT name FROM employees', sqlite_runner())
        self.assertFalse(r.passed)

    def test_wrong_rows_score_zero_and_name_the_extra_rows(self):
        r = grade(task('SELECT name FROM employees WHERE salary >= 5000'),
                  'SELECT name FROM employees WHERE salary >= 4000', sqlite_runner())
        self.assertFalse(r.passed)
        self.assertEqual(score(r), Decimal('0.00'))
        self.assertIn('precise', codes(r, passed=False))
        self.assertTrue(r.feedback['extra_rows'])

    def test_missing_rows_are_named(self):
        r = grade(task('SELECT name FROM employees'),
                  "SELECT name FROM employees WHERE name <> 'Шевченко'", sqlite_runner())
        self.assertIn('Шевченко', ' '.join(r.feedback['hints']))
        self.assertTrue(r.feedback['missing_rows'])

    def test_column_count_mismatch_scores_zero(self):
        r = grade(task('SELECT name FROM employees'),
                  'SELECT name, salary FROM employees', sqlite_runner())
        self.assertEqual(score(r), Decimal('0.00'))
        self.assertIn('columns', codes(r, passed=False))

    def test_avg_instead_of_sum(self):
        r = grade(task('SELECT SUM(salary) FROM employees'),
                  'SELECT AVG(salary) FROM employees', sqlite_runner())
        self.assertFalse(r.passed)
        self.assertEqual(score(r), Decimal('0.00'))


class HardcodeTests(unittest.TestCase):
    def test_constant_answer_scores_zero(self):
        student = ("SELECT 'Розробка', 2 UNION ALL SELECT 'Аналітика', 2 "
                   "UNION ALL SELECT 'Підтримка', 1")
        r = grade(task(COUNT_PER_DEPT, hidden=[EMPTY_DEPT]), student, sqlite_runner())
        self.assertFalse(r.passed)
        self.assertEqual(score(r), Decimal('0.00'))
        self.assertIn('reads_data', codes(r, passed=False))

    def test_hardcode_also_fails_hidden_datasets(self):
        r = grade(task('SELECT name FROM departments', hidden=[EMPTY_DEPT]),
                  "SELECT 'Розробка' UNION ALL SELECT 'Аналітика' UNION ALL SELECT 'Підтримка'",
                  sqlite_runner())
        failed = codes(r, passed=False)
        self.assertIn('reads_data', failed)
        self.assertIn('dataset:1', failed)


class ExecutionErrorTests(unittest.TestCase):
    def test_sql_error_scores_zero_with_message(self):
        r = grade(task('SELECT name FROM employees'), 'SELEC name FROM employees',
                  sqlite_runner())
        self.assertFalse(r.passed)
        self.assertEqual(score(r), Decimal('0.00'))
        self.assertFalse(r.execution.success)
        self.assertIn('execution', codes(r, passed=False))
        self.assertTrue(r.execution.error)

    def test_two_statements_are_rejected_without_running(self):
        calls = []
        r = grade(task('SELECT name FROM employees'),
                  'SELECT name FROM employees; DROP TABLE employees',
                  sqlite_runner(calls))
        self.assertEqual(calls, [])
        self.assertIn('execution', codes(r, passed=False))
        self.assertIn('одна інструкція', r.feedback['hints'][0])

    def test_semicolon_inside_a_literal_is_not_a_second_statement(self):
        r = grade(task("SELECT ';' AS sep, name FROM employees"),
                  "SELECT ';' AS sep, name FROM employees", sqlite_runner())
        self.assertTrue(r.passed)
        self.assertNotIn('shape', codes(r))

    def test_reference_error_is_blamed_on_the_task(self):
        r = grade(task('SELECT nope FROM employees'), 'SELECT name FROM employees',
                  sqlite_runner())
        self.assertFalse(r.passed)
        self.assertTrue(any('викладача' in h for h in r.feedback['hints']))


class OrderingTests(unittest.TestCase):
    REF = 'SELECT name FROM employees ORDER BY salary DESC'

    def test_order_by_in_reference_makes_order_graded(self):
        r = grade(task(self.REF), 'SELECT name FROM employees ORDER BY salary ASC',
                  sqlite_runner())
        self.assertFalse(r.passed)
        self.assertEqual(score(r), Decimal('0.00'))
        self.assertIn('order', codes(r, passed=False))
        self.assertEqual(r.feedback['passed_count'], r.feedback['total'] - 1)

    def test_correct_order_passes(self):
        r = grade(task(self.REF), 'SELECT name FROM employees ORDER BY salary DESC',
                  sqlite_runner())
        self.assertTrue(r.passed)

    def test_no_order_by_in_reference_means_any_order_is_fine(self):
        r = grade(task('SELECT name FROM employees'),
                  'SELECT name FROM employees ORDER BY salary ASC', sqlite_runner())
        self.assertTrue(r.passed)

    def test_manual_order_matters_flag_is_respected(self):
        r = grade(task('SELECT name FROM employees', order_matters=True),
                  'SELECT name FROM employees ORDER BY salary ASC', sqlite_runner())
        self.assertFalse(r.passed)

    def test_wrong_rows_fail_order_with_reason(self):
        r = grade(task(self.REF), 'SELECT name FROM employees WHERE salary > 5000 ORDER BY 1',
                  sqlite_runner())
        order = next(c for c in r.feedback['criteria'] if c['id'] == 'order')
        self.assertEqual(order['detail'], 'Спершу виправте набір рядків.')
        self.assertEqual(score(r), Decimal('0.00'))


class StructureTests(unittest.TestCase):
    REF = COUNT_PER_DEPT
    OK = ("SELECT d.name, COUNT(e.id) FROM departments d "
          "LEFT JOIN employees e ON e.dept_id = d.id GROUP BY d.name")

    def test_required_construct_present(self):
        r = grade(task(self.REF, required_keywords=['LEFT JOIN', 'GROUP BY']), self.OK,
                  sqlite_runner())
        self.assertTrue(r.passed)
        self.assertEqual(r.feedback['keywords_missing'], [])

    def test_required_construct_missing(self):
        r = grade(task('SELECT name FROM employees WHERE dept_id = 1',
                       required_keywords=['JOIN']),
                  'SELECT name FROM employees WHERE dept_id = 1', sqlite_runner())
        self.assertFalse(r.passed)
        self.assertEqual(r.feedback['keywords_missing'], ['JOIN'])
        self.assertEqual(score(r), Decimal('0.00'))

    def test_keyword_inside_string_literal_does_not_count(self):
        r = grade(task("SELECT 'JOIN' AS x, name FROM employees", required_keywords=['JOIN']),
                  "SELECT 'JOIN' AS x, name FROM employees", sqlite_runner())
        self.assertEqual(r.feedback['keywords_missing'], ['JOIN'])

    def test_forbidden_construct_used(self):
        r = grade(task(self.REF, forbidden_keywords=['LEFT JOIN']), self.OK, sqlite_runner())
        self.assertFalse(r.passed)
        self.assertEqual(r.feedback['forbidden_used'], ['LEFT JOIN'])

    def test_keyword_outside_ast_vocabulary_falls_back_to_text(self):
        q = 'SELECT name FROM employees WHERE salary BETWEEN 4000 AND 6000'
        r = grade(task(q, required_keywords=['BETWEEN']), q, sqlite_runner())
        self.assertTrue(r.passed)

    def test_forbidden_keyword_in_comment_does_not_count(self):
        q = 'SELECT name FROM employees -- no JOIN here'
        r = grade(task('SELECT name FROM employees', forbidden_keywords=['JOIN']), q,
                  sqlite_runner())
        self.assertEqual(r.feedback['forbidden_used'], [])


class ReferenceModesTests(unittest.TestCase):
    def test_snapshot_is_used_when_no_reference_query(self):
        t = task('', expected_result={'columns': ['name'], 'rows': [['Іваненко']]})
        r = grade(t, "SELECT name FROM employees WHERE id = 1", sqlite_runner())
        self.assertTrue(r.passed)

    def test_hidden_datasets_are_skipped_without_reference_query(self):
        t = task('', hidden=[EMPTY_DEPT],
                 expected_result={'columns': ['name'], 'rows': [['Іваненко']]})
        r = grade(t, "SELECT name FROM employees WHERE id = 1", sqlite_runner())
        self.assertTrue(r.passed)
        self.assertEqual(r.feedback['failed_datasets'], [])

    def test_free_exercise_without_any_reference_passes_on_execution(self):
        r = grade(task(''), 'SELECT name FROM employees', sqlite_runner())
        self.assertTrue(r.passed)
        self.assertEqual(score(r), Decimal('100.00'))

    def test_free_exercise_still_checks_required_keywords(self):
        r = grade(task('', required_keywords=['GROUP BY']), 'SELECT name FROM employees',
                  sqlite_runner())
        self.assertFalse(r.passed)


class TruncationTests(unittest.TestCase):
    def fake(self, truncated_student=True, diff_rows=None, diff_ok=True):
        calls = []

        def run(sql, ds, purpose):
            calls.append(purpose)
            if purpose == PURPOSE_DIFF:
                return Execution(diff_ok, ['x'], diff_rows or [], error='' if diff_ok else 'boom')
            rows = [[i] for i in range(3)]
            return Execution(True, ['n'], rows, truncated=(purpose == PURPOSE_STUDENT and truncated_student))
        return run, calls

    def test_sqlite_cannot_grade_a_truncated_result(self):
        run, _ = self.fake()
        r = grade(task('SELECT id FROM employees'), 'SELECT id FROM employees', run)
        self.assertFalse(r.passed)
        self.assertEqual(score(r), Decimal('0.00'))
        self.assertTrue(any('завеликий' in h for h in r.feedback['hints']))

    def test_postgres_uses_in_database_difference_when_truncated(self):
        run, calls = self.fake()
        r = grade(task('SELECT id FROM employees', db_type='postgresql'),
                  'SELECT id FROM employees', run)
        self.assertTrue(r.passed)
        self.assertIn(PURPOSE_DIFF, calls)

    def test_non_empty_difference_means_wrong(self):
        run, _ = self.fake(diff_rows=[[1]])
        r = grade(task('SELECT id FROM employees', db_type='postgresql'),
                  'SELECT id FROM employees', run)
        self.assertFalse(r.passed)


class InDatabaseDifferenceTests(unittest.TestCase):
    def test_hidden_datasets_use_one_diff_call_each_on_postgres(self):
        calls = []

        def run(sql, ds, purpose):
            calls.append((purpose, ds.name))
            if purpose == PURPOSE_DIFF:
                return Execution(True, ['x'], [])
            return Execution(True, ['name'], [['a']])

        r = grade(task('SELECT name FROM employees', db_type='postgresql',
                       hidden=[EMPTY_DEPT, NOBODY]),
                  'SELECT name FROM employees', run)
        self.assertTrue(r.passed)
        diff_calls = [d for p, d in calls if p == PURPOSE_DIFF]
        self.assertEqual(diff_calls, ['порожній відділ', 'порожня вибірка'])

    def test_diff_failure_falls_back_to_python_comparison(self):
        calls = []

        def run(sql, ds, purpose):
            calls.append((purpose, ds.name))
            if purpose == PURPOSE_DIFF:
                return Execution(False, error='UNION types text and integer cannot be matched')
            return Execution(True, ['name'], [['a']])

        r = grade(task('SELECT name FROM employees', db_type='postgresql', hidden=[NOBODY]),
                  'SELECT name FROM employees', run)
        self.assertTrue(r.passed)
        self.assertIn((PURPOSE_REFERENCE, 'порожня вибірка'), calls)


class NoSqlTests(unittest.TestCase):
    def test_mongodb_documents_match_regardless_of_key_order_and_id(self):
        def run(sql, ds, purpose):
            if purpose == PURPOSE_STUDENT:
                doc = {'_id': 'aaa', 'name': 'Іваненко', 'age': 30}
            else:
                doc = {'age': 30, 'name': 'Іваненко', '_id': 'bbb'}
            return Execution(True, ['result'], [[json.dumps(doc)]])

        r = grade(task('db.users.find({})', db_type='mongodb'), 'db.users.find({})', run)
        self.assertTrue(r.passed)

    def test_mongodb_different_documents_fail(self):
        def run(sql, ds, purpose):
            doc = {'name': 'A'} if purpose == PURPOSE_STUDENT else {'name': 'B'}
            return Execution(True, ['result'], [[json.dumps(doc)]])

        r = grade(task('db.users.find({})', db_type='mongodb'), 'db.users.find({})', run)
        self.assertFalse(r.passed)

    def test_redis_values_compare_as_strings(self):
        def run(sql, ds, purpose):
            return Execution(True, ['value'], [['42']])

        r = grade(task('GET counter', db_type='redis'), 'GET counter', run)
        self.assertTrue(r.passed)


class DmlTests(unittest.TestCase):
    def test_same_number_of_affected_rows_passes(self):
        q = 'UPDATE employees SET salary = salary + 1'
        r = grade(task(q, query_type='update'), q, sqlite_runner())
        self.assertTrue(r.passed)
        self.assertEqual(r.feedback['mode'], 'execution')

    def test_different_number_of_affected_rows_fails(self):
        r = grade(task('UPDATE employees SET salary = salary + 1', query_type='update'),
                  'UPDATE employees SET salary = salary + 1 WHERE dept_id = 1',
                  sqlite_runner())
        self.assertFalse(r.passed)
        self.assertIn('state', codes(r, passed=False))

    def test_dml_syntax_error_scores_zero(self):
        r = grade(task('DELETE FROM employees', query_type='delete'),
                  'DELETE FROM nope', sqlite_runner())
        self.assertEqual(score(r), Decimal('0.00'))


class ScoreShapeTests(unittest.TestCase):
    def test_score_is_decimal_with_two_places(self):
        r = grade(task('SELECT name FROM employees'), 'SELECT name FROM employees',
                  sqlite_runner())
        self.assertIsInstance(r.score, Decimal)
        self.assertEqual(r.score.as_tuple().exponent, -2)

    def test_max_score_scales_the_result(self):
        r = grade(task('SELECT name FROM employees', max_score=10),
                  'SELECT name FROM employees', sqlite_runner())
        self.assertEqual(r.score, Decimal('10.00'))

    def test_feedback_has_frontend_fields(self):
        r = grade(task('SELECT name FROM employees'), 'SELECT name FROM employees',
                  sqlite_runner())
        for key in ('message', 'hints', 'checks', 'keywords_missing', 'forbidden_used',
                    'result_match', 'mode'):
            self.assertIn(key, r.feedback)


if __name__ == '__main__':
    unittest.main()
