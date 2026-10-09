"""Data-changing tasks, NoSQL databases and exercises without a reference query."""

import unittest

from grading.criteria import evaluate
from grading.service import Execution, GradingTask, PURPOSE_REFERENCE, PURPOSE_STUDENT
from grading.test_service import sqlite_runner, sqlite_sequence_runner
from grading.test_criteria import PRIMARY
from grading.test_criteria_eval import company, detail, verdicts


class DmlTests(unittest.TestCase):
    def test_equivalent_update_passes_state(self):
        t = company('UPDATE employees SET salary = salary * 2 WHERE dept_id = 1')
        r = evaluate(t, 'UPDATE employees SET salary = salary + salary WHERE dept_id = 1',
                     sqlite_runner(), sqlite_sequence_runner())
        self.assertEqual(verdicts(r), {'execution': True, 'state': True})
        self.assertTrue(r.passed)

    def test_delete_does_not_pass_an_update_exercise(self):
        t = company('UPDATE employees SET salary = 0 WHERE dept_id = 1')
        r = evaluate(t, 'DELETE FROM employees WHERE dept_id = 1',
                     sqlite_runner(), sqlite_sequence_runner())
        self.assertFalse(verdicts(r)['state'])
        self.assertIn('employees', detail(r, 'state'))

    def test_dml_syntax_error_fails_both(self):
        t = company('DELETE FROM employees WHERE dept_id = 1')
        r = evaluate(t, 'DELETE FROM', sqlite_runner(), sqlite_sequence_runner())
        self.assertEqual(verdicts(r), {'execution': False, 'state': False})

    def test_without_sequence_runner_affected_rows_decide(self):
        t = company('DELETE FROM employees WHERE dept_id = 1')
        r = evaluate(t, 'DELETE FROM employees WHERE dept_id = 2', sqlite_runner())
        self.assertTrue(verdicts(r)['state'])   # both delete two rows; legacy fallback only
        r2 = evaluate(t, 'DELETE FROM employees WHERE dept_id = 3', sqlite_runner())
        self.assertFalse(verdicts(r2)['state'])

    def test_create_table_compares_the_new_table(self):
        t = company('CREATE TABLE archive AS SELECT * FROM employees WHERE dept_id = 1')
        r = evaluate(t, 'CREATE TABLE archive AS SELECT * FROM employees WHERE dept_id = 2',
                     sqlite_runner(), sqlite_sequence_runner())
        self.assertFalse(verdicts(r)['state'])
        self.assertIn('archive', detail(r, 'state'))

    def test_keywords_apply_to_dml(self):
        t = company('DELETE FROM employees WHERE dept_id = 1', required_keywords=['WHERE'])
        r = evaluate(t, 'DELETE FROM employees', sqlite_runner(), sqlite_sequence_runner())
        self.assertFalse(verdicts(r)['require:WHERE'])


class NoSqlTests(unittest.TestCase):
    def mongo_runner(self, rows_by_purpose):
        def run(query, dataset, purpose):
            return Execution(True, ['document'], rows_by_purpose[purpose])
        return run

    def test_documents_match_regardless_of_key_order_and_id(self):
        t = GradingTask(db_type='mongodb', reference_query='db.t.find({})', primary=PRIMARY,
                        required_keywords=['find'])
        run = self.mongo_runner({
            PURPOSE_STUDENT: [['{"_id": "a1", "x": 1, "y": 2}']],
            PURPOSE_REFERENCE: [['{"y": 2, "x": 1, "_id": "b2"}']],
        })
        r = evaluate(t, 'db.t.find({})', run)
        # No ORDER BY exists for NoSQL, so order is graded only when the instructor asks.
        self.assertEqual(verdicts(r), {'execution': True, 'columns': True, 'complete': True,
                                       'precise': True, 'require:find': True})

    def test_different_documents_fail(self):
        t = GradingTask(db_type='mongodb', reference_query='db.t.find({})', primary=PRIMARY)
        run = self.mongo_runner({PURPOSE_STUDENT: [['{"x": 1}']],
                                 PURPOSE_REFERENCE: [['{"x": 2}']]})
        r = evaluate(t, 'db.t.find({x: 1})', run)
        self.assertFalse(verdicts(r)['complete'])
        self.assertFalse(verdicts(r)['precise'])


class ReferenceModesTests(unittest.TestCase):
    def test_snapshot_is_used_when_no_reference_query(self):
        t = company('', expected_result={'columns': ['name'],
                                         'rows': [['Іваненко'], ['Петренко']]})
        r = evaluate(t, 'SELECT name FROM employees WHERE dept_id = 1', sqlite_runner())
        self.assertTrue(r.passed)
        self.assertNotIn('order', verdicts(r))

    def test_free_exercise_passes_on_execution(self):
        r = evaluate(company(''), 'SELECT 1', sqlite_runner())
        self.assertEqual(verdicts(r), {'execution': True, 'reads_data': False})
        self.assertFalse(r.passed)   # constant answers never pass, even without a reference
        r2 = evaluate(company(''), 'SELECT name FROM employees', sqlite_runner())
        self.assertTrue(r2.passed)
