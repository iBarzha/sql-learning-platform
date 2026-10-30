"""Criteria for row order by sort keys, value-type hints, column order and hidden rows."""

import unittest
from types import SimpleNamespace

from grading.criteria import MSG, evaluate
from grading.service import Execution, GradingTask, PURPOSE_DIFF, PURPOSE_REFERENCE
from grading.test_criteria_eval import company, detail, verdicts
from grading.test_service import EMPTY_DEPT, PRIMARY, sqlite_runner, sqlite_sequence_runner


def fixed_runner(student_rows, reference_rows, columns=('name', 'dept_id'), calls=None):
    """Every reference run returns `reference_rows`, every other run `student_rows`."""
    def run(sql, dataset, purpose):
        if calls is not None:
            calls.append(purpose)
        if purpose == PURPOSE_DIFF:
            return Execution(True, ['x'], [])
        rows = reference_rows if purpose == PURPOSE_REFERENCE else student_rows
        return Execution(True, list(columns), [list(r) for r in rows])
    return run


class OrderBySortKeysTests(unittest.TestCase):
    REFERENCE = 'SELECT name, dept_id FROM employees ORDER BY dept_id'
    EXPECTED = [['a', 1], ['b', 1], ['c', 2]]

    def test_rows_tied_on_the_sort_key_may_come_in_any_order(self):
        r = evaluate(company(self.REFERENCE), 'SELECT name, dept_id FROM employees',
                     fixed_runner([['b', 1], ['a', 1], ['c', 2]], self.EXPECTED))
        self.assertTrue(verdicts(r)['order'])

    def test_rows_in_a_different_key_order_fail_order(self):
        r = evaluate(company(self.REFERENCE), 'SELECT name, dept_id FROM employees',
                     fixed_runner([['c', 2], ['a', 1], ['b', 1]], self.EXPECTED))
        self.assertFalse(verdicts(r)['order'])
        self.assertEqual(detail(r, 'order'), MSG['order'])

    def test_strict_fallback_fails_swapped_tied_rows_when_the_key_is_not_selected(self):
        # ORDER BY dept_id cannot be mapped to an output column, so whole rows are compared.
        r = evaluate(company('SELECT name FROM employees ORDER BY dept_id'),
                     'SELECT name FROM employees',
                     fixed_runner([['b'], ['a']], [['a'], ['b']], columns=('name',)))
        self.assertFalse(verdicts(r)['order'])

    def test_strict_fallback_for_order_matters_without_order_by(self):
        r = evaluate(company('SELECT name, dept_id FROM employees', order_matters=True),
                     'SELECT name, dept_id FROM employees',
                     fixed_runner([['b', 1], ['a', 1]], [['a', 1], ['b', 1]]))
        self.assertFalse(verdicts(r)['order'])

    def test_real_database_ties_pass_either_way(self):
        for student in ('SELECT name, dept_id FROM employees ORDER BY dept_id, name',
                        'SELECT name, dept_id FROM employees ORDER BY dept_id, name DESC'):
            r = evaluate(company(self.REFERENCE), student, sqlite_runner())
            self.assertTrue(verdicts(r)['order'], student)


class TypeOnlyHintTests(unittest.TestCase):
    def test_number_as_text_gets_the_type_hint_and_still_fails(self):
        r = evaluate(company('SELECT COUNT(*) FROM employees'), "SELECT '5' FROM employees",
                     fixed_runner([['5']], [[5]], columns=('n',)))
        self.assertFalse(verdicts(r)['complete'])
        self.assertFalse(verdicts(r)['precise'])
        self.assertEqual(detail(r, 'complete'), MSG['type_only'])
        self.assertEqual(detail(r, 'precise'), MSG['type_only'])

    def test_wrong_value_keeps_the_row_list(self):
        r = evaluate(company('SELECT COUNT(*) FROM employees'), "SELECT '6' FROM employees",
                     fixed_runner([['6']], [[5]], columns=('n',)))
        self.assertEqual(detail(r, 'complete'), 'Не вистачає рядків: (5).')


class ColumnOrderTests(unittest.TestCase):
    REFERENCE = 'SELECT name, salary FROM employees'
    SWAPPED = 'SELECT salary, name FROM employees'

    def test_swapped_columns_pass_only_with_the_flag(self):
        strict = evaluate(company(self.REFERENCE), self.SWAPPED, sqlite_runner())
        self.assertFalse(verdicts(strict)['complete'])
        tolerant = evaluate(company(self.REFERENCE, ignore_column_order=True), self.SWAPPED,
                            sqlite_runner())
        self.assertTrue(verdicts(tolerant)['complete'])
        self.assertTrue(verdicts(tolerant)['precise'])

    def test_column_names_follow_the_permutation(self):
        t = company(self.REFERENCE, ignore_column_order=True,
                    criteria={'enabled': ['column_names', 'complete']})
        self.assertTrue(verdicts(evaluate(t, self.SWAPPED, sqlite_runner()))['column_names'])
        r = evaluate(t, 'SELECT salary AS pay, name FROM employees', sqlite_runner())
        self.assertEqual(detail(r, 'column_names'), 'Стовпець 2: очікується salary, отримано pay.')

    def test_order_is_checked_after_the_permutation(self):
        t = company(self.REFERENCE + ' ORDER BY salary', ignore_column_order=True)
        right = evaluate(t, self.SWAPPED + ' ORDER BY salary', sqlite_runner())
        self.assertTrue(verdicts(right)['order'])
        wrong = evaluate(t, self.SWAPPED + ' ORDER BY salary DESC', sqlite_runner())
        self.assertFalse(verdicts(wrong)['order'])
        self.assertEqual(detail(wrong, 'order'), MSG['order'])

    def test_hidden_datasets_are_compared_in_python(self):
        calls = []
        t = GradingTask(db_type='postgresql', reference_query='SELECT name, id FROM employees',
                        primary=PRIMARY, hidden=[EMPTY_DEPT], ignore_column_order=True)
        r = evaluate(t, 'SELECT id, name FROM employees',
                     fixed_runner([[1, 'a']], [['a', 1]], calls=calls))
        self.assertTrue(verdicts(r)['dataset:1'])
        self.assertNotIn(PURPOSE_DIFF, calls)

    def test_build_task_passes_the_flag(self):
        from grading.runner import build_task
        dataset = SimpleNamespace(schema_sql='', seed_sql='')
        task = build_task('sqlite', reference_query='SELECT 1', dataset=dataset,
                          check_datasets=[], ignore_column_order=True)
        self.assertTrue(task.ignore_column_order)
        self.assertFalse(build_task('sqlite', reference_query='SELECT 1', dataset=dataset,
                                    check_datasets=[]).ignore_column_order)


class HiddenRowsTests(unittest.TestCase):
    def test_missing_and_extra_rows_are_counted_not_listed(self):
        r = evaluate(company('SELECT name FROM employees WHERE salary > 5000'),
                     'SELECT name FROM employees WHERE salary < 5000', sqlite_runner(),
                     reveal_rows=False)
        self.assertEqual(detail(r, 'complete'), 'Не вистачає рядків: 3.')
        self.assertEqual(detail(r, 'precise'), 'Зайві рядки: 2.')

    def test_table_state_is_counted_not_listed(self):
        t = company('UPDATE employees SET salary = 0 WHERE dept_id = 1')
        r = evaluate(t, 'DELETE FROM employees WHERE dept_id = 1', sqlite_runner(),
                     sqlite_sequence_runner(), reveal_rows=False)
        self.assertEqual(detail(r, 'state'), 'таблиця employees: бракує рядків 2, зайвих 0.')


if __name__ == '__main__':
    unittest.main()
