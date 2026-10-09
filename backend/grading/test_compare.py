"""Unit tests for multiset result comparison. No database required."""

import unittest
from decimal import Decimal

from grading.compare import (
    KIND_COLUMN_COUNT,
    KIND_OK,
    KIND_ORDER,
    KIND_ROWS,
    KIND_TRUNCATED,
    compare,
)


def _cols(rows, given):
    if given is not None:
        return given
    return ['c'] * len(rows[0]) if rows else ['c']


def cmp(student_rows, expected_rows, *, student_cols=None, expected_cols=None, **kw):
    return compare(
        _cols(student_rows, student_cols), student_rows,
        _cols(expected_rows, expected_cols), expected_rows,
        **kw,
    )


class IdentityTests(unittest.TestCase):
    def test_identical_results_match(self):
        diff = cmp([['a'], ['b']], [['a'], ['b']])
        self.assertTrue(diff.equal)
        self.assertEqual(diff.kind, KIND_OK)

    def test_empty_results_match(self):
        diff = compare(['c'], [], ['c'], [])
        self.assertTrue(diff.equal)

    def test_overlap_is_one_when_equal(self):
        self.assertEqual(cmp([['a']], [['a']]).overlap, 1.0)


class DuplicateTests(unittest.TestCase):
    """The regression that made a correct answer score 50 and read as wrong."""

    def test_duplicate_rows_are_preserved(self):
        diff = cmp([['Kyiv'], ['Kyiv']], [['Kyiv'], ['Kyiv']])
        self.assertTrue(diff.equal)

    def test_missing_one_duplicate_is_detected(self):
        diff = cmp([['Kyiv']], [['Kyiv'], ['Kyiv']])
        self.assertFalse(diff.equal)
        self.assertEqual(len(diff.missing), 1)

    def test_extra_duplicate_is_detected(self):
        diff = cmp([['Kyiv'], ['Kyiv']], [['Kyiv']])
        self.assertFalse(diff.equal)
        self.assertEqual(len(diff.extra), 1)

    def test_distinct_against_duplicates_fails(self):
        diff = cmp([['a'], ['b']], [['a'], ['a'], ['b']])
        self.assertFalse(diff.equal)

    def test_same_row_count_different_multiplicity_fails(self):
        diff = cmp([['a'], ['a'], ['b']], [['a'], ['b'], ['b']])
        self.assertFalse(diff.equal)
        self.assertEqual(diff.kind, KIND_ROWS)


class ColumnTests(unittest.TestCase):
    def test_column_names_are_ignored(self):
        diff = compare(['full_name'], [['Ivan']], ['name'], [['Ivan']])
        self.assertTrue(diff.equal)

    def test_column_count_mismatch_is_reported(self):
        diff = compare(['a', 'b'], [['x', 'y']], ['a'], [['x']])
        self.assertFalse(diff.equal)
        self.assertEqual(diff.kind, KIND_COLUMN_COUNT)
        self.assertEqual(diff.student_columns, 2)
        self.assertEqual(diff.expected_columns, 1)

    def test_column_order_is_significant(self):
        diff = compare(['a', 'b'], [['x', 'y']], ['b', 'a'], [['x', 'y']])
        self.assertTrue(diff.equal)  # positional: same tuple, same result
        swapped = compare(['a', 'b'], [['y', 'x']], ['b', 'a'], [['x', 'y']])
        self.assertFalse(swapped.equal)


class TypeTests(unittest.TestCase):
    def test_decimal_matches_int_across_engines(self):
        diff = cmp([[Decimal('10.00')]], [[10]])
        self.assertTrue(diff.equal)

    def test_bool_matches_one(self):
        diff = cmp([[True]], [[1]])
        self.assertTrue(diff.equal)

    def test_null_is_matched_against_null(self):
        diff = cmp([[None]], [[None]])
        self.assertTrue(diff.equal)

    def test_null_does_not_match_empty_string(self):
        diff = cmp([[None]], [['']])
        self.assertFalse(diff.equal)


class OrderTests(unittest.TestCase):
    def test_permutation_matches_when_order_is_not_graded(self):
        diff = cmp([['b'], ['a']], [['a'], ['b']], ordered=False)
        self.assertTrue(diff.equal)

    def test_permutation_fails_when_order_is_graded(self):
        diff = cmp([['b'], ['a']], [['a'], ['b']], ordered=True)
        self.assertFalse(diff.equal)
        self.assertEqual(diff.kind, KIND_ORDER)

    def test_order_failure_still_reports_full_overlap(self):
        diff = cmp([['b'], ['a']], [['a'], ['b']], ordered=True)
        self.assertEqual(diff.overlap, 1.0)

    def test_correct_order_passes(self):
        diff = cmp([['a'], ['b']], [['a'], ['b']], ordered=True)
        self.assertTrue(diff.equal)

    def test_wrong_rows_report_rows_not_order(self):
        diff = cmp([['a'], ['c']], [['a'], ['b']], ordered=True)
        self.assertEqual(diff.kind, KIND_ROWS)


class OverlapTests(unittest.TestCase):
    def test_one_of_two_rows_right_and_one_wrong(self):
        # Jaccard: 1 matched / (2 + 2 - 1) = 1/3
        diff = cmp([['a'], ['x']], [['a'], ['b']])
        self.assertAlmostEqual(diff.overlap, 1 / 3)

    def test_no_overlap(self):
        diff = cmp([['x'], ['y']], [['a'], ['b']])
        self.assertEqual(diff.overlap, 0.0)

    def test_superset_is_penalized(self):
        expected = [['a'], ['b']]
        superset = [['a'], ['b'], ['c'], ['d'], ['e'], ['f']]
        self.assertAlmostEqual(cmp(superset, expected).overlap, 2 / 6)

    def test_missing_half_scores_half(self):
        diff = cmp([['a']], [['a'], ['b']])
        self.assertAlmostEqual(diff.overlap, 0.5)

    def test_expected_empty_but_student_returned_rows(self):
        diff = compare(['c'], [['a']], ['c'], [])
        self.assertFalse(diff.equal)
        self.assertEqual(diff.overlap, 0.0)

    def test_expected_empty_and_student_empty(self):
        diff = compare(['c'], [], ['c'], [])
        self.assertTrue(diff.equal)
        self.assertEqual(diff.overlap, 1.0)


class TruncationTests(unittest.TestCase):
    """A truncated result is an arbitrary subset, so no verdict is safe."""

    def test_truncated_student_is_not_graded_as_equal(self):
        diff = cmp([['a']], [['a']], student_truncated=True)
        self.assertFalse(diff.equal)
        self.assertEqual(diff.kind, KIND_TRUNCATED)

    def test_truncated_expected_is_not_graded_as_equal(self):
        diff = cmp([['a']], [['a']], expected_truncated=True)
        self.assertEqual(diff.kind, KIND_TRUNCATED)

    def test_column_mismatch_is_reported_before_truncation(self):
        diff = compare(['a', 'b'], [['x', 'y']], ['a'], [['x']], student_truncated=True)
        self.assertEqual(diff.kind, KIND_COLUMN_COUNT)


class DiagnosticsTests(unittest.TestCase):
    def test_missing_rows_are_listed(self):
        diff = cmp([['a']], [['a'], ['b']])
        self.assertIn('b', diff.describe_missing())

    def test_extra_rows_are_listed(self):
        diff = cmp([['a'], ['b']], [['a']])
        self.assertIn('b', diff.describe_extra())

    def test_preview_is_capped(self):
        expected = [[str(i)] for i in range(10)]
        diff = compare(['c'], [], ['c'], expected)
        text = diff.describe_missing(limit=3)
        self.assertIn('ще 7', text)

    def test_diagnostics_are_deterministic(self):
        first = cmp([['a']], [['c'], ['b'], ['a']]).describe_missing()
        second = cmp([['a']], [['b'], ['c'], ['a']]).describe_missing()
        self.assertEqual(first, second)


if __name__ == '__main__':
    unittest.main()
