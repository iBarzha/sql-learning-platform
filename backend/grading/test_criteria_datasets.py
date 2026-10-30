"""Derived criteria: hidden datasets (with time budget and truncation) and keywords."""

import unittest

from grading import criteria as mod
from grading.criteria import MSG, evaluate
from grading.service import Execution, GradingTask
from grading.test_service import (
    BOUNDARY,
    COUNT_PER_DEPT,
    EMPTY_DEPT,
    NOBODY,
    PURPOSE_DIFF,
    sqlite_runner,
)
from grading.test_criteria import PRIMARY
from grading.test_criteria_eval import company, detail, verdicts


class HiddenDatasetTests(unittest.TestCase):
    def test_inner_join_fails_only_the_dataset_criterion(self):
        t = company(hidden=[EMPTY_DEPT])
        r = evaluate(t, "SELECT d.name, COUNT(e.id) FROM departments d JOIN employees e "
                        "ON e.dept_id = d.id GROUP BY d.name", sqlite_runner())
        self.assertEqual(verdicts(r)['complete'], True)
        self.assertEqual(verdicts(r)['dataset:1'], False)
        self.assertEqual(detail(r, 'dataset:1'), 'відділ без працівників')

    def test_each_dataset_is_its_own_criterion(self):
        t = company('SELECT name FROM employees WHERE salary >= 5000', hidden=[BOUNDARY, NOBODY])
        r = evaluate(t, 'SELECT name FROM employees WHERE salary > 5000', sqlite_runner())
        self.assertEqual(verdicts(r)['dataset:1'], False)
        self.assertEqual(verdicts(r)['dataset:2'], True)

    def test_datasets_still_run_when_primary_rows_differ(self):
        calls = []
        t = company('SELECT name FROM employees WHERE salary >= 5000', hidden=[NOBODY])
        r = evaluate(t, 'SELECT name FROM employees WHERE salary > 100000', sqlite_runner(calls))
        # primary student + primary reference, then the hidden dataset (student + reference)
        self.assertEqual(len(calls), 4)
        self.assertFalse(verdicts(r)['complete'])
        self.assertTrue(verdicts(r)['dataset:1'])   # both queries are empty on "порожня вибірка"

    def test_datasets_do_not_run_when_column_count_differs(self):
        calls = []
        t = company(hidden=[EMPTY_DEPT])
        r = evaluate(t, 'SELECT name FROM departments', sqlite_runner(calls))
        self.assertEqual(len(calls), 2)   # student + reference on the primary dataset only
        self.assertEqual(detail(r, 'dataset:1'), 'Кількість стовпців не збігається.')

    def test_budget_exhaustion_fails_remaining_datasets(self):
        original = mod.HIDDEN_BUDGET_SECONDS
        mod.HIDDEN_BUDGET_SECONDS = -1.0
        try:
            t = company(hidden=[EMPTY_DEPT, BOUNDARY])
            r = evaluate(t, COUNT_PER_DEPT, sqlite_runner())
        finally:
            mod.HIDDEN_BUDGET_SECONDS = original
        self.assertFalse(verdicts(r)['dataset:1'])
        self.assertEqual(detail(r, 'dataset:2'), MSG['budget'])
        self.assertFalse(r.passed)


class KeywordTests(unittest.TestCase):
    def test_required_construct_from_ast(self):
        t = company(required_keywords=['LEFT JOIN', 'GROUP BY'])
        r = evaluate(t, COUNT_PER_DEPT, sqlite_runner())
        self.assertTrue(verdicts(r)['require:LEFT JOIN'])
        self.assertTrue(verdicts(r)['require:GROUP BY'])

    def test_keyword_inside_comment_does_not_count(self):
        t = company('SELECT name FROM employees', required_keywords=['WHERE'])
        r = evaluate(t, 'SELECT name FROM employees', sqlite_runner())
        self.assertFalse(verdicts(r)['require:WHERE'])
        r2 = evaluate(t, 'SELECT name FROM employees -- WHERE', sqlite_runner())
        self.assertFalse(verdicts(r2)['require:WHERE'])

    def test_keyword_inside_string_literal_does_not_count(self):
        t = company("SELECT name FROM employees", required_keywords=['LEFT JOIN'])
        r = evaluate(t, "SELECT name FROM employees WHERE name <> 'LEFT JOIN'", sqlite_runner())
        self.assertFalse(verdicts(r)['require:LEFT JOIN'])

    def test_forbidden_subquery(self):
        t = company('SELECT name FROM employees WHERE dept_id = 1',
                    forbidden_keywords=['SUBQUERY'])
        r = evaluate(t, "SELECT name FROM employees WHERE dept_id IN (SELECT id FROM departments "
                        "WHERE name = 'Розробка')", sqlite_runner())
        self.assertFalse(verdicts(r)['forbid:SUBQUERY'])
        self.assertEqual(detail(r, 'forbid:SUBQUERY'), 'Використано заборонене SUBQUERY.')


class TruncationTests(unittest.TestCase):
    def fake_runner(self, diff_rows, student_truncated=True):
        def run(sql, dataset, purpose):
            if purpose == PURPOSE_DIFF:
                return Execution(True, ['a'], diff_rows)
            return Execution(True, ['a'], [[1]], truncated=student_truncated)
        return run

    def test_sqlite_cannot_decide_a_truncated_result(self):
        r = evaluate(company('SELECT a FROM t'), 'SELECT a FROM t', self.fake_runner([]))
        self.assertFalse(verdicts(r)['complete'])
        self.assertEqual(detail(r, 'complete'), MSG['truncated'])

    def test_postgres_decides_in_database(self):
        t = GradingTask(db_type='postgresql', reference_query='SELECT a FROM t ORDER BY a',
                        primary=PRIMARY)
        r = evaluate(t, 'SELECT a FROM t', self.fake_runner([]))
        self.assertTrue(verdicts(r)['complete'] and verdicts(r)['precise'])
        self.assertEqual(detail(r, 'order'), MSG['truncated_order'])
        r2 = evaluate(t, 'SELECT a FROM t', self.fake_runner([[5]]))
        self.assertFalse(verdicts(r2)['complete'])
        self.assertEqual(detail(r2, 'complete'), MSG['mismatch'])


class BudgetClockTests(unittest.TestCase):
    def test_budget_counts_from_the_start_of_grading(self):
        """A slow primary phase leaves less time for hidden datasets, not a fresh 45 s."""
        from unittest import mock
        # Context creation reads the clock at 0; by the first hidden dataset 46 s passed.
        ticks = iter([0.0, 46.0, 46.0, 46.0, 46.0, 46.0])
        with mock.patch('grading.criteria.time.monotonic', side_effect=lambda: next(ticks)):
            t = company(hidden=[EMPTY_DEPT])
            r = evaluate(t, COUNT_PER_DEPT, sqlite_runner())
        self.assertEqual(detail(r, 'dataset:1'), MSG['budget'])
