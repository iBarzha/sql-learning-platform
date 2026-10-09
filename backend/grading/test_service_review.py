"""Regression tests for the issues found in the adversarial review of the grading core."""

import unittest
from decimal import Decimal

from grading import service as service_module
from grading import criteria as criteria_module
from grading.service import (
    CheckDataset,
    Execution,
    GradingTask,
    PURPOSE_DIFF,
    PURPOSE_REFERENCE,
    PURPOSE_STUDENT,
    grade,
)
from grading.test_service import (
    EMPTY_DEPT,
    NOBODY,
    codes,
    sqlite_runner,
    sqlite_sequence_runner,
    task,
)


class DmlLessonExerciseTests(unittest.TestCase):
    """Lesson exercises carry query_type='select'; the reference must decide the mode."""

    def test_delete_does_not_pass_an_update_exercise(self):
        # Both statements touch all 5 rows; only the table state tells them apart.
        r = grade(task('UPDATE employees SET salary = salary + 1'),
                  'DELETE FROM employees', sqlite_runner(), sqlite_sequence_runner())
        self.assertFalse(r.passed)
        self.assertEqual(r.feedback['mode'], 'execution')
        self.assertIn('state', codes(r, passed=False))

    def test_matching_update_passes_via_execution_mode(self):
        q = 'UPDATE employees SET salary = salary + 1'
        r = grade(task(q), q, sqlite_runner(), sqlite_sequence_runner())
        self.assertTrue(r.passed)
        self.assertEqual(r.feedback['mode'], 'execution')
        self.assertIn('state', codes(r, passed=True))

    def test_equivalent_update_written_differently_passes(self):
        r = grade(task("UPDATE employees SET salary = salary * 2 WHERE dept_id = 1"),
                  "UPDATE employees SET salary = salary + salary WHERE dept_id IN (SELECT id FROM departments WHERE name = 'Розробка')",
                  sqlite_runner(), sqlite_sequence_runner())
        self.assertTrue(r.passed, r.feedback)

    def test_update_without_where_fails_when_reference_filters(self):
        r = grade(task('UPDATE employees SET salary = salary + 100 WHERE dept_id = 1'),
                  'UPDATE employees SET salary = salary + 100',
                  sqlite_runner(), sqlite_sequence_runner())
        self.assertFalse(r.passed)
        self.assertTrue(any('employees' in h for h in r.feedback['hints']))

    def test_insert_with_wrong_values_fails(self):
        ref = "INSERT INTO departments VALUES (4, 'Кадри')"
        self.assertTrue(grade(task(ref), ref, sqlite_runner(), sqlite_sequence_runner()).passed)
        r = grade(task(ref), "INSERT INTO departments VALUES (4, 'Маркетинг')",
                  sqlite_runner(), sqlite_sequence_runner())
        self.assertFalse(r.passed)

    def test_create_table_task_compares_the_new_table(self):
        ref = 'CREATE TABLE projects (id INTEGER PRIMARY KEY, title TEXT)'
        self.assertTrue(grade(task(ref), 'CREATE TABLE projects (id INTEGER PRIMARY KEY, title TEXT)',
                              sqlite_runner(), sqlite_sequence_runner()).passed)
        r = grade(task(ref), 'CREATE TABLE projects (id INTEGER PRIMARY KEY)',
                  sqlite_runner(), sqlite_sequence_runner())
        self.assertFalse(r.passed)

    def test_dropping_a_table_is_caught(self):
        r = grade(task('DELETE FROM employees WHERE id = 1'), 'DROP TABLE employees',
                  sqlite_runner(), sqlite_sequence_runner())
        self.assertFalse(r.passed)

    def test_without_sequence_runner_affected_rows_are_used(self):
        r = grade(task('UPDATE employees SET salary = salary + 1'),
                  'UPDATE employees SET salary = salary + 1 WHERE dept_id = 1', sqlite_runner())
        self.assertFalse(r.passed)
        self.assertIn('state', codes(r, passed=False))

    def test_dml_answer_to_a_select_task_is_rejected_without_running(self):
        calls = []
        r = grade(task('SELECT name FROM employees'), 'DELETE FROM employees',
                  sqlite_runner(calls))
        self.assertEqual(calls, [])
        self.assertIn('execution', codes(r, passed=False))
        self.assertEqual(r.score, Decimal('0.00'))

    def test_select_reference_with_no_result_columns_is_not_a_pass(self):
        def run(sql, ds, purpose):
            return Execution(True, [], [])
        r = grade(task('SELECT name FROM employees'), 'SELECT name FROM employees', run)
        self.assertFalse(r.passed)


class ConstantReferenceTests(unittest.TestCase):
    def test_constant_reference_is_not_flagged_as_hardcode(self):
        r = grade(task('SELECT 2 + 2'), 'SELECT 4', sqlite_runner())
        self.assertTrue(r.passed, r.feedback)
        self.assertNotIn('hardcode', codes(r))

    def test_table_valued_function_answer_is_not_hardcode(self):
        def run(sql, ds, purpose):
            return Execution(True, ['g'], [[1], [2], [3]])
        r = grade(task('SELECT g FROM generate_series(1, 3) AS g', db_type='postgresql'),
                  'SELECT g FROM generate_series(1, 3) AS g', run)
        self.assertTrue(r.passed, r.feedback)


class SnapshotTests(unittest.TestCase):
    def test_legacy_snapshot_with_stringified_decimals_matches(self):
        t = task('', expected_result={'columns': ['total'], 'rows': [['25500.00']]})
        r = grade(t, 'SELECT SUM(salary) FROM employees', sqlite_runner())
        self.assertTrue(r.passed, r.feedback)

    def test_live_reference_stays_strict_about_text_vs_number(self):
        r = grade(task("SELECT '25500' AS total"), 'SELECT 25500 AS total', sqlite_runner())
        self.assertFalse(r.passed)


class PartialCreditTests(unittest.TestCase):
    def test_dumping_the_whole_table_scores_zero(self):
        r = grade(task('SELECT name FROM employees WHERE salary >= 5000'),
                  'SELECT name FROM employees', sqlite_runner())
        self.assertFalse(r.passed)
        self.assertEqual(r.score, Decimal('0.00'))
        self.assertEqual(codes(r, passed=False), {'precise'})


class CompositionRobustnessTests(unittest.TestCase):
    def test_render_failure_falls_back_to_python_comparison(self):
        original = criteria_module.build_symmetric_difference

        def boom(*args, **kwargs):
            raise RuntimeError('sqlglot exploded')

        criteria_module.build_symmetric_difference = boom
        try:
            calls = []

            def run(sql, ds, purpose):
                calls.append(purpose)
                return Execution(True, ['name'], [['a']])

            r = grade(task('SELECT name FROM employees', db_type='postgresql', hidden=[NOBODY]),
                      'SELECT name FROM employees', run)
        finally:
            criteria_module.build_symmetric_difference = original

        self.assertTrue(r.passed, r.feedback)
        self.assertNotIn(PURPOSE_DIFF, calls)
        self.assertIn(PURPOSE_REFERENCE, calls)


class TimeoutTests(unittest.TestCase):
    def test_timed_out_difference_is_a_failure_without_retry(self):
        calls = []

        def run(sql, ds, purpose):
            calls.append((purpose, ds.name))
            if purpose == PURPOSE_DIFF:
                return Execution(False, error='Query exceeded 10s timeout')
            return Execution(True, ['name'], [['a']])

        r = grade(task('SELECT name FROM employees', db_type='postgresql', hidden=[EMPTY_DEPT]),
                  'SELECT name FROM employees', run)
        self.assertFalse(r.passed)
        self.assertEqual(r.feedback['failed_datasets'][0]['name'], EMPTY_DEPT.name)
        # No second student run and no reference run on the hidden dataset.
        self.assertEqual([c for c in calls if c[1] == EMPTY_DEPT.name], [(PURPOSE_DIFF, EMPTY_DEPT.name)])

    def test_hidden_budget_stops_checking_and_does_not_pass(self):
        original = criteria_module.HIDDEN_BUDGET_SECONDS
        # Negative so the very first monotonic() check is already "over budget"
        # regardless of clock resolution.
        criteria_module.HIDDEN_BUDGET_SECONDS = -1.0
        try:
            calls = []

            def run(sql, ds, purpose):
                calls.append(ds.name)
                return Execution(True, ['name'], [['a']])

            hidden = [CheckDataset(f'h{i}', '', '') for i in range(3)]
            r = grade(task('SELECT name FROM employees', hidden=hidden),
                      'SELECT name FROM employees', run)
        finally:
            criteria_module.HIDDEN_BUDGET_SECONDS = original

        self.assertFalse(r.passed)
        self.assertTrue(any('не встигли' in h for h in r.feedback['hints']))
        self.assertNotIn('h2', calls)


class MongoIdTests(unittest.TestCase):
    def test_only_top_level_id_is_ignored(self):
        def run(sql, ds, purpose):
            if purpose == PURPOSE_STUDENT:
                doc = '{"_id": "a", "order": {"_id": 1, "total": 5}}'
            else:
                doc = '{"_id": "b", "order": {"_id": 2, "total": 5}}'
            return Execution(True, ['result'], [[doc]])

        r = grade(task('db.o.find({})', db_type='mongodb'), 'db.o.find({})', run)
        self.assertFalse(r.passed)


if __name__ == '__main__':
    unittest.main()
