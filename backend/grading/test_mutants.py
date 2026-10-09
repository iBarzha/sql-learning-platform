"""Unit tests for mutant generation and dataset validation."""

import unittest

from grading.mutants import generate_mutants, validate_datasets
from grading.service import Execution
from grading.test_service import (
    BOUNDARY,
    COUNT_PER_DEPT,
    EMPTY_DEPT,
    NOBODY,
    PRIMARY,
    sqlite_runner,
)


def kinds(mutants):
    return {m.kind for m in mutants}


def sqls(mutants):
    return [m.sql for m in mutants]


class GenerateMutantsTests(unittest.TestCase):
    def test_left_join_becomes_inner(self):
        mutants = generate_mutants(COUNT_PER_DEPT, 'sqlite')
        self.assertIn('join_type', kinds(mutants))
        self.assertTrue(any('LEFT JOIN' not in m.sql and 'JOIN' in m.sql
                            for m in mutants if m.kind == 'join_type'))

    def test_inner_join_becomes_left(self):
        mutants = generate_mutants(
            'SELECT d.name FROM departments d JOIN employees e ON e.dept_id = d.id', 'sqlite')
        self.assertTrue(any('LEFT JOIN' in m.sql for m in mutants if m.kind == 'join_type'))

    def test_comparison_operators_are_swapped(self):
        mutants = generate_mutants('SELECT name FROM employees WHERE salary >= 5000', 'sqlite')
        self.assertIn('SELECT name FROM employees WHERE salary > 5000', sqls(mutants))

    def test_distinct_is_removed_when_present(self):
        mutants = generate_mutants('SELECT DISTINCT name FROM employees', 'sqlite')
        self.assertIn('SELECT name FROM employees', sqls(mutants))

    def test_distinct_is_added_when_absent(self):
        mutants = generate_mutants('SELECT name FROM employees', 'sqlite')
        self.assertIn('SELECT DISTINCT name FROM employees', sqls(mutants))

    def test_distinct_is_not_added_to_a_grouped_query(self):
        # DISTINCT is a no-op after GROUP BY; the mutant would be equivalent noise.
        mutants = generate_mutants(COUNT_PER_DEPT, 'sqlite')
        self.assertFalse(any('DISTINCT' in m.sql for m in mutants))

    def test_distinct_is_not_added_to_a_bare_aggregate(self):
        mutants = generate_mutants('SELECT COUNT(*) AS n, MAX(salary) FROM employees', 'sqlite')
        self.assertFalse(any('DISTINCT' in m.sql for m in mutants))

    def test_distinct_is_still_added_when_a_column_is_selected_with_an_aggregate(self):
        mutants = generate_mutants('SELECT dept_id, COUNT(*) FROM employees', 'sqlite')
        self.assertTrue(any('DISTINCT' in m.sql for m in mutants))

    def test_each_where_conjunct_is_dropped(self):
        mutants = generate_mutants(
            'SELECT name FROM employees WHERE salary > 1 AND dept_id = 2', 'sqlite')
        self.assertIn('SELECT name FROM employees WHERE dept_id = 2', sqls(mutants))
        self.assertIn('SELECT name FROM employees WHERE salary > 1', sqls(mutants))
        self.assertIn('SELECT name FROM employees', sqls(mutants))

    def test_and_or_swap(self):
        mutants = generate_mutants(
            'SELECT name FROM employees WHERE salary > 1 AND dept_id = 2', 'sqlite')
        self.assertIn('SELECT name FROM employees WHERE salary > 1 OR dept_id = 2', sqls(mutants))

    def test_count_column_becomes_count_star(self):
        mutants = generate_mutants('SELECT COUNT(bonus) FROM employees', 'sqlite')
        self.assertIn('SELECT COUNT(*) FROM employees', sqls(mutants))

    def test_aggregates_are_swapped(self):
        mutants = generate_mutants('SELECT SUM(salary) FROM employees', 'sqlite')
        self.assertIn('SELECT AVG(salary) FROM employees', sqls(mutants))

    def test_having_and_limit_are_removed(self):
        mutants = generate_mutants(
            'SELECT dept_id FROM employees GROUP BY dept_id HAVING COUNT(*) > 1 LIMIT 2',
            'sqlite')
        self.assertIn('having', kinds(mutants))
        self.assertIn('limit', kinds(mutants))

    def test_reference_itself_is_never_a_mutant(self):
        q = 'SELECT name FROM employees WHERE salary >= 5000'
        self.assertNotIn(q, sqls(generate_mutants(q, 'sqlite')))

    def test_mutants_are_unique(self):
        mutants = generate_mutants(COUNT_PER_DEPT, 'sqlite')
        self.assertEqual(len(sqls(mutants)), len(set(sqls(mutants))))


class ValidateDatasetsTests(unittest.TestCase):
    def test_primary_alone_cannot_tell_inner_from_left_join(self):
        report = validate_datasets(COUNT_PER_DEPT, [PRIMARY], sqlite_runner(), 'sqlite')
        self.assertIn('join_type', kinds(report.surviving))

    def test_empty_department_dataset_kills_the_join_mutant(self):
        report = validate_datasets(COUNT_PER_DEPT, [PRIMARY, EMPTY_DEPT], sqlite_runner(),
                                   'sqlite')
        self.assertNotIn('join_type', kinds(report.surviving))

    def test_boundary_dataset_kills_the_comparison_mutant(self):
        q = 'SELECT name FROM employees WHERE salary >= 5000'
        without = validate_datasets(q, [PRIMARY], sqlite_runner(), 'sqlite')
        with_boundary = validate_datasets(q, [PRIMARY, BOUNDARY], sqlite_runner(), 'sqlite')
        survivor = 'SELECT name FROM employees WHERE salary > 5000'
        self.assertIn(survivor, sqls(without.surviving))
        self.assertNotIn(survivor, sqls(with_boundary.surviving))

    def test_reference_empty_datasets_are_reported(self):
        report = validate_datasets('SELECT name FROM employees WHERE salary >= 5000',
                                   [PRIMARY, NOBODY], sqlite_runner(), 'sqlite')
        self.assertEqual(report.reference_empty_on, ['порожня вибірка'])

    def test_killed_count_is_consistent(self):
        report = validate_datasets(COUNT_PER_DEPT, [PRIMARY, EMPTY_DEPT], sqlite_runner(),
                                   'sqlite')
        self.assertEqual(report.killed + len(report.surviving), report.mutants_total)

    def test_erroring_mutant_counts_as_killed(self):
        def run(sql, ds, purpose):
            if purpose == 'mutant':
                return Execution(False, error='syntax error')
            return Execution(True, ['name'], [['a']])

        report = validate_datasets('SELECT name FROM employees WHERE salary > 1', [PRIMARY],
                                   run, 'sqlite')
        self.assertEqual(report.surviving, [])

    def test_reference_error_is_reported_per_dataset(self):
        report = validate_datasets('SELECT nope FROM employees', [PRIMARY], sqlite_runner(),
                                   'sqlite')
        self.assertIn('основний', report.reference_errors)


if __name__ == '__main__':
    unittest.main()
