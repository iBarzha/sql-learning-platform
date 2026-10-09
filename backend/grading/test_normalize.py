"""Unit tests for value canonicalization. No database required."""

import datetime as dt
import unittest
import uuid
from decimal import Decimal

from grading.normalize import (
    NULL,
    canonical_json,
    describe_row,
    describe_value,
    normalize_row,
    normalize_rows,
    normalize_value,
)


def same(a, b) -> bool:
    return normalize_value(a) == normalize_value(b)


class NullTests(unittest.TestCase):
    def test_none_becomes_null_sentinel(self):
        self.assertIs(normalize_value(None), NULL)

    def test_null_equals_itself(self):
        self.assertTrue(same(None, None))

    def test_null_is_not_empty_string(self):
        self.assertFalse(same(None, ''))

    def test_null_is_not_zero(self):
        self.assertFalse(same(None, 0))

    def test_null_is_hashable_for_counter_use(self):
        self.assertEqual(len({normalize_value(None), normalize_value(None)}), 1)


class NumericTests(unittest.TestCase):
    def test_decimal_matches_int(self):
        self.assertTrue(same(Decimal('10.00'), 10))

    def test_float_matches_int(self):
        self.assertTrue(same(10.0, 10))

    def test_decimal_matches_float(self):
        self.assertTrue(same(Decimal('2.5'), 2.5))

    def test_float_representation_error_is_absorbed(self):
        self.assertTrue(same(0.1 + 0.2, 0.3))

    def test_distinct_numbers_stay_distinct(self):
        self.assertFalse(same(10, 11))

    def test_difference_below_tolerance_collapses(self):
        self.assertTrue(same(1.0000000001, 1.0))

    def test_difference_above_tolerance_is_kept(self):
        self.assertFalse(same(1.001, 1.0))

    def test_large_integer_does_not_raise(self):
        self.assertTrue(same(10 ** 40, 10 ** 40))

    def test_large_integers_stay_distinct(self):
        self.assertFalse(same(10 ** 40, 10 ** 40 + 1))

    def test_negative_zero_matches_zero(self):
        self.assertTrue(same(-0.0, 0))

    def test_nan_collapses_so_counter_comparison_works(self):
        self.assertTrue(same(float('nan'), float('nan')))

    def test_positive_and_negative_infinity_differ(self):
        self.assertFalse(same(float('inf'), float('-inf')))

    def test_infinity_is_not_a_finite_number(self):
        self.assertFalse(same(float('inf'), 10 ** 40))


class BooleanTests(unittest.TestCase):
    def test_true_matches_one(self):
        self.assertTrue(same(True, 1))

    def test_false_matches_zero(self):
        self.assertTrue(same(False, 0))

    def test_true_does_not_match_zero(self):
        self.assertFalse(same(True, 0))


class StringTests(unittest.TestCase):
    def test_char_padding_is_ignored(self):
        self.assertTrue(same('Київ  ', 'Київ'))

    def test_leading_whitespace_is_significant(self):
        self.assertFalse(same('  Київ', 'Київ'))

    def test_case_is_significant(self):
        self.assertFalse(same('київ', 'Київ'))

    def test_numeric_string_is_not_a_number(self):
        # PostgreSQL refuses to match text against integer in a set operation,
        # so the Python path must not be more permissive than EXCEPT ALL.
        self.assertFalse(same('10', 10))


class TemporalTests(unittest.TestCase):
    def test_date_matches_equal_date(self):
        self.assertTrue(same(dt.date(2026, 9, 6), dt.date(2026, 9, 6)))

    def test_different_dates_differ(self):
        self.assertFalse(same(dt.date(2026, 9, 6), dt.date(2026, 9, 7)))

    def test_aware_datetime_is_converted_to_utc(self):
        tz = dt.timezone(dt.timedelta(hours=3))
        aware = dt.datetime(2026, 9, 6, 15, 0, tzinfo=tz)
        naive_utc = dt.datetime(2026, 9, 6, 12, 0)
        self.assertTrue(same(aware, naive_utc))

    def test_time_is_supported(self):
        self.assertTrue(same(dt.time(10, 30), dt.time(10, 30)))

    def test_timedelta_becomes_seconds(self):
        self.assertTrue(same(dt.timedelta(minutes=1), 60))


class BinaryAndIdentifierTests(unittest.TestCase):
    def test_bytes_match_bytearray(self):
        self.assertTrue(same(b'\x01\x02', bytearray(b'\x01\x02')))

    def test_bytes_are_not_strings(self):
        self.assertFalse(same(b'ab', 'ab'))

    def test_uuid_matches_its_text_form(self):
        value = uuid.uuid4()
        self.assertTrue(same(value, str(value)))


class JsonTests(unittest.TestCase):
    def test_key_order_does_not_matter(self):
        self.assertTrue(same({'a': 1, 'b': 2}, {'b': 2, 'a': 1}))

    def test_nested_key_order_does_not_matter(self):
        self.assertTrue(same({'x': {'a': 1, 'b': 2}}, {'x': {'b': 2, 'a': 1}}))

    def test_different_documents_differ(self):
        self.assertFalse(same({'a': 1}, {'a': 2}))

    def test_list_order_is_significant(self):
        self.assertFalse(same([1, 2], [2, 1]))

    def test_drop_keys_removes_mongo_id(self):
        left = canonical_json({'_id': 'aaa', 'name': 'x'}, drop_keys=['_id'])
        right = canonical_json({'_id': 'bbb', 'name': 'x'}, drop_keys=['_id'])
        self.assertEqual(left, right)

    def test_drop_keys_is_recursive(self):
        left = canonical_json({'d': {'_id': 1, 'v': 2}}, drop_keys=['_id'])
        right = canonical_json({'d': {'_id': 9, 'v': 2}}, drop_keys=['_id'])
        self.assertEqual(left, right)

    def test_canonical_json_is_stable(self):
        self.assertEqual(canonical_json({'b': 1, 'a': 2}), canonical_json({'a': 2, 'b': 1}))


class RowTests(unittest.TestCase):
    def test_row_becomes_hashable_tuple(self):
        row = normalize_row([1, 'x', None])
        self.assertIsInstance(row, tuple)
        hash(row)

    def test_rows_normalize_elementwise(self):
        self.assertEqual(normalize_rows([[1], [2]]), [normalize_row([1]), normalize_row([2])])

    def test_equal_rows_from_different_engines_match(self):
        postgres_row = [Decimal('10.00'), True, 'Київ  ']
        mariadb_row = [10, 1, 'Київ']
        self.assertEqual(normalize_row(postgres_row), normalize_row(mariadb_row))


class DescribeTests(unittest.TestCase):
    def test_null_is_readable(self):
        self.assertEqual(describe_value(normalize_value(None)), 'NULL')

    def test_number_is_readable(self):
        self.assertEqual(describe_value(normalize_value(10)), '10')

    def test_nan_is_readable(self):
        self.assertEqual(describe_value(normalize_value(float('nan'))), 'NaN')

    def test_row_is_readable(self):
        self.assertEqual(describe_row(normalize_row(['Київ', 3])), '(Київ, 3)')


if __name__ == '__main__':
    unittest.main()
