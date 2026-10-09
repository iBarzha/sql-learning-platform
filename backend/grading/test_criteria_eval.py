"""Criteria evaluation on a real in-memory SQLite database: SELECT tasks and thresholds."""

import unittest

from grading.criteria import evaluate
from grading.service import GradingTask
from grading.test_service import (
    COUNT_PER_DEPT,
    EMPTY_DEPT,
    sqlite_runner,
)
from grading.test_service import PRIMARY as COMPANY


def company(reference=COUNT_PER_DEPT, **kw):
    return GradingTask(db_type='sqlite', reference_query=reference, primary=COMPANY, **kw)


def verdicts(result):
    return {item['id']: item['passed'] for item in result.items}


def detail(result, cid):
    return next(item['detail'] for item in result.items if item['id'] == cid)


class SelectEvaluationTests(unittest.TestCase):
    def test_correct_answer_passes_every_default_criterion(self):
        r = evaluate(company(), COUNT_PER_DEPT, sqlite_runner())
        self.assertEqual(verdicts(r), {'execution': True, 'columns': True, 'complete': True,
                                       'precise': True, 'reads_data': True})
        self.assertEqual((r.passed_count, r.total, r.threshold, r.passed), (5, 5, 5, True))

    def test_execution_error_fails_everything_with_one_reason(self):
        r = evaluate(company(), 'SELECT nope FROM nowhere', sqlite_runner())
        self.assertFalse(any(verdicts(r).values()))
        self.assertIn('no such table', detail(r, 'execution'))
        self.assertEqual(detail(r, 'complete'), 'Запит не виконався.')

    def test_two_statements_fail_execution_without_running(self):
        calls = []
        r = evaluate(company(), 'SELECT 1; SELECT 2', sqlite_runner(calls))
        self.assertFalse(r.passed)
        self.assertEqual(calls, [])
        self.assertIn('одна інструкція', detail(r, 'execution'))

    def test_dml_answer_to_select_task_fails_execution_without_running(self):
        calls = []
        r = evaluate(company(), 'DELETE FROM employees', sqlite_runner(calls))
        self.assertEqual(calls, [])
        self.assertIn('SELECT', detail(r, 'execution'))

    def test_column_count_mismatch_fails_result_criteria_only(self):
        r = evaluate(company(), 'SELECT name FROM departments', sqlite_runner())
        self.assertEqual(verdicts(r), {'execution': True, 'columns': False, 'complete': False,
                                       'precise': False, 'reads_data': True})
        self.assertEqual(detail(r, 'columns'), 'Очікується 2 стовпці, отримано 1.')
        self.assertEqual(detail(r, 'complete'), 'Кількість стовпців не збігається.')

    def test_missing_rows_fail_complete_but_not_precise(self):
        r = evaluate(company(),
                     "SELECT d.name, COUNT(e.id) FROM departments d LEFT JOIN employees e "
                     "ON e.dept_id = d.id WHERE d.id <> 3 GROUP BY d.name", sqlite_runner())
        self.assertEqual(verdicts(r)['complete'], False)
        self.assertEqual(verdicts(r)['precise'], True)
        self.assertIn('Підтримка', detail(r, 'complete'))

    def test_extra_rows_fail_precise_but_not_complete(self):
        r = evaluate(company('SELECT name FROM employees WHERE salary > 5000'),
                     'SELECT name FROM employees', sqlite_runner())
        self.assertEqual(verdicts(r)['complete'], True)
        self.assertEqual(verdicts(r)['precise'], False)
        self.assertIn('Зайві рядки', detail(r, 'precise'))

    def test_column_names_fail_alone(self):
        t = company('SELECT name AS employee FROM employees',
                    criteria={'enabled': ['columns', 'column_names', 'complete', 'precise']})
        r = evaluate(t, 'SELECT name FROM employees', sqlite_runner())
        self.assertEqual(verdicts(r), {'execution': True, 'columns': True, 'column_names': False,
                                       'complete': True, 'precise': True})
        self.assertEqual(detail(r, 'column_names'),
                         'Стовпець 1: очікується employee, отримано name.')

    def test_column_names_ignore_case(self):
        t = company('SELECT name AS Employee FROM employees',
                    criteria={'enabled': ['column_names']})
        r = evaluate(t, 'SELECT name AS EMPLOYEE FROM employees', sqlite_runner())
        self.assertTrue(verdicts(r)['column_names'])

    def test_wrong_order_fails_only_order(self):
        r = evaluate(company('SELECT name FROM employees ORDER BY salary DESC'),
                     'SELECT name FROM employees ORDER BY salary', sqlite_runner())
        self.assertEqual(verdicts(r)['order'], False)
        self.assertEqual(verdicts(r)['complete'], True)
        self.assertEqual(detail(r, 'order'), 'Рядки правильні, але порядок інший.')

    def test_order_fails_with_reason_when_rows_are_wrong(self):
        r = evaluate(company('SELECT name FROM employees ORDER BY salary DESC'),
                     'SELECT name FROM employees WHERE salary > 5000 ORDER BY salary DESC',
                     sqlite_runner())
        self.assertEqual(detail(r, 'order'), 'Спершу виправте набір рядків.')

    def test_hardcoded_answer_fails_reads_data_only(self):
        r = evaluate(company('SELECT name FROM departments'),
                     "SELECT 'Розробка' UNION ALL SELECT 'Аналітика' UNION ALL SELECT 'Підтримка'",
                     sqlite_runner())
        self.assertEqual(verdicts(r)['reads_data'], False)
        self.assertEqual(verdicts(r)['complete'], True)

    def test_unparseable_query_is_graded_by_execution_only(self):
        # sqlglot cannot parse this SQLite-only syntax, the engine runs it fine.
        r = evaluate(company('SELECT name FROM employees', required_keywords=['WHERE']),
                     "SELECT name FROM employees WHERE name GLOB 'І*' OR 1 = 1", sqlite_runner())
        self.assertTrue(verdicts(r)['execution'])
        self.assertTrue(verdicts(r)['reads_data'])
        self.assertTrue(verdicts(r)['require:WHERE'])

    def test_reference_failure_blames_the_task(self):
        r = evaluate(company('SELECT nope FROM employees'), 'SELECT name FROM employees',
                     sqlite_runner())
        self.assertTrue(verdicts(r)['execution'])
        self.assertFalse(verdicts(r)['complete'])
        self.assertIn('Еталонний запит', detail(r, 'complete'))


class ThresholdTests(unittest.TestCase):
    def test_threshold_met_passes(self):
        t = company('SELECT name FROM employees ORDER BY salary DESC', criteria={'threshold': 5})
        r = evaluate(t, 'SELECT name FROM employees ORDER BY salary', sqlite_runner())
        self.assertEqual((r.passed_count, r.total, r.threshold), (5, 6, 5))
        self.assertTrue(r.passed)

    def test_threshold_not_met_fails(self):
        t = company('SELECT name FROM employees ORDER BY salary DESC', criteria={'threshold': 6})
        r = evaluate(t, 'SELECT name FROM employees ORDER BY salary', sqlite_runner())
        self.assertFalse(r.passed)

    def test_threshold_above_total_means_all(self):
        t = company(criteria={'threshold': 40})
        r = evaluate(t, COUNT_PER_DEPT, sqlite_runner())
        self.assertEqual(r.threshold, r.total)
        self.assertTrue(r.passed)

    def test_items_keep_catalog_order_then_derived(self):
        t = company(hidden=[EMPTY_DEPT], required_keywords=['LEFT JOIN'],
                    criteria={'enabled': ['precise', 'columns']})
        r = evaluate(t, COUNT_PER_DEPT, sqlite_runner())
        self.assertEqual([i['id'] for i in r.items],
                         ['execution', 'columns', 'precise', 'dataset:1', 'require:LEFT JOIN'])
