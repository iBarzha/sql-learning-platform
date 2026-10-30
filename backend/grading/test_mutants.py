"""Unit tests for mutant generation and dataset validation."""

import unittest

import sqlglot

from grading.mutants import MAX_MUTANTS, generate_mutants, validate_datasets
from grading.service import Execution
from grading.test_service import (
    BOUNDARY,
    COUNT_PER_DEPT,
    EMPTY_DEPT,
    NOBODY,
    PRIMARY,
    sqlite_runner,
)


OLD_KINDS = frozenset({'join_type', 'comparison', 'aggregate', 'count', 'distinct', 'where',
                       'logic', 'having', 'limit'})


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


def canonical(sql):
    return sqlglot.parse_one(sql, read='sqlite').sql(dialect='sqlite')


class NewMutationClassTests(unittest.TestCase):
    def of_kind(self, reference, kind):
        return [(m.description, canonical(m.sql))
                for m in generate_mutants(reference, 'sqlite') if m.kind == kind]

    def test_is_null_becomes_is_not_null(self):
        self.assertEqual(self.of_kind('SELECT name FROM employees WHERE bonus IS NULL', 'null_test'),
                         [('IS NULL замінено на IS NOT NULL',
                           canonical('SELECT name FROM employees WHERE bonus IS NOT NULL'))])

    def test_is_not_null_becomes_is_null(self):
        self.assertEqual(
            self.of_kind('SELECT name FROM employees WHERE bonus IS NOT NULL', 'null_test'),
            [('IS NOT NULL замінено на IS NULL',
              canonical('SELECT name FROM employees WHERE bonus IS NULL'))])

    def test_between_becomes_strict(self):
        self.assertEqual(
            self.of_kind('SELECT name FROM employees WHERE salary BETWEEN 4000 AND 6000',
                         'between'),
            [('межі BETWEEN зроблено строгими',
              canonical('SELECT name FROM employees WHERE salary > 4000 AND salary < 6000'))])

    def test_not_between_keeps_the_strict_range_together(self):
        self.assertEqual(
            self.of_kind('SELECT name FROM employees WHERE NOT salary BETWEEN 4000 AND 6000',
                         'between'),
            [('межі BETWEEN зроблено строгими',
              canonical('SELECT name FROM employees WHERE NOT (salary > 4000 AND salary < 6000)'))])

    def test_like_wildcards_are_removed(self):
        self.assertEqual(
            self.of_kind("SELECT name FROM employees WHERE name LIKE 'І_ан%'", 'like'),
            [('прибрано символи підстановки з шаблону LIKE',
              canonical("SELECT name FROM employees WHERE name LIKE 'Іан'"))])

    def test_like_with_only_wildcards_is_skipped(self):
        self.assertEqual(
            self.of_kind("SELECT name FROM employees WHERE name LIKE '%'", 'like'), [])

    def test_each_group_by_expression_is_dropped(self):
        reference = 'SELECT dept_id, name, COUNT(*) FROM employees GROUP BY dept_id, name'
        self.assertEqual(self.of_kind(reference, 'group_by'), [
            ('прибрано вираз №1 з GROUP BY',
             canonical('SELECT dept_id, name, COUNT(*) FROM employees GROUP BY name')),
            ('прибрано вираз №2 з GROUP BY',
             canonical('SELECT dept_id, name, COUNT(*) FROM employees GROUP BY dept_id')),
        ])

    def test_single_group_by_expression_is_kept(self):
        self.assertEqual(self.of_kind(COUNT_PER_DEPT, 'group_by'), [])

    def test_join_condition_is_dropped(self):
        self.assertEqual(
            self.of_kind('SELECT e.name FROM employees e JOIN departments d ON d.id = e.dept_id',
                         'join_condition'),
            [("прибрано умову з'єднання",
              canonical('SELECT e.name FROM employees e CROSS JOIN departments d'))])

    def test_not_is_dropped(self):
        self.assertEqual(
            self.of_kind('SELECT name FROM departments d WHERE NOT EXISTS '
                         '(SELECT 1 FROM employees e WHERE e.dept_id = d.id)', 'not'),
            [('прибрано NOT', canonical('SELECT name FROM departments d WHERE EXISTS '
                                        '(SELECT 1 FROM employees e WHERE e.dept_id = d.id)'))])

    def test_not_in_and_is_not_null_are_left_to_their_own_classes(self):
        reference = 'SELECT name FROM employees WHERE dept_id NOT IN (1, 2) AND bonus IS NOT NULL'
        self.assertEqual(self.of_kind(reference, 'not'), [])
        self.assertEqual(self.of_kind(reference, 'in_not_in'), [])

    def test_in_becomes_not_in(self):
        self.assertEqual(
            self.of_kind('SELECT name FROM employees WHERE dept_id IN (1, 2)', 'in_not_in'),
            [('IN замінено на NOT IN',
              canonical('SELECT name FROM employees WHERE dept_id NOT IN (1, 2)'))])

    def test_gruber_reference_stays_within_the_cap_with_old_classes_first(self):
        mutants = generate_mutants(
            'SELECT snum, SUM(amt) FROM Orders GROUP BY snum '
            'HAVING SUM(amt) > (SELECT MAX(amt) FROM Orders)', 'sqlite')
        self.assertLessEqual(len(mutants), MAX_MUTANTS)
        self.assertEqual([m.kind for m in mutants][:2], ['comparison', 'aggregate'])
        self.assertTrue(all(m.kind in OLD_KINDS for m in mutants))

    def test_new_classes_come_after_the_existing_ones(self):
        mutants = generate_mutants(
            'SELECT name FROM employees WHERE salary >= 5000 AND bonus IS NULL', 'sqlite')
        order = [m.kind for m in mutants]
        self.assertLess(max(i for i, k in enumerate(order) if k in OLD_KINDS),
                        min(i for i, k in enumerate(order) if k not in OLD_KINDS))


class ValidationWarningTests(unittest.TestCase):
    NO_HIDDEN = ('У вправи немає прихованих наборів: відповідь, що формально читає таблицю, '
                 'але містить готові значення, пройде перевірку.')

    def test_clean_reference_with_hidden_datasets_has_no_warnings(self):
        report = validate_datasets(COUNT_PER_DEPT, [PRIMARY, EMPTY_DEPT], sqlite_runner(),
                                   'sqlite')
        self.assertEqual(report.warnings, [])

    def test_single_dataset_is_warned_about(self):
        report = validate_datasets(COUNT_PER_DEPT, [PRIMARY], sqlite_runner(), 'sqlite')
        self.assertEqual(report.warnings, [self.NO_HIDDEN])

    def test_limit_without_order_by_is_warned_about(self):
        report = validate_datasets('SELECT name FROM employees LIMIT 2', [PRIMARY, EMPTY_DEPT],
                                   sqlite_runner(), 'sqlite')
        self.assertEqual(report.warnings,
                         ['LIMIT без ORDER BY: набір рядків може відрізнятися між запусками.'])

    def test_nondeterministic_function_is_warned_about(self):
        report = validate_datasets('SELECT name, RANDOM() FROM employees', [PRIMARY, EMPTY_DEPT],
                                   sqlite_runner(), 'sqlite')
        self.assertEqual(len(report.warnings), 1)
        self.assertIn('rand()', report.warnings[0])


if __name__ == '__main__':
    unittest.main()
