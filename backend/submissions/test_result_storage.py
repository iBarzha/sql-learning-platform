"""Stored submission results must survive JSON encoding whatever the engine returned."""

import datetime as dt
import json
from decimal import Decimal

from django.test import SimpleTestCase

from submissions.storage import json_safe


class JsonSafeTests(SimpleTestCase):
    def test_decimals_become_numbers(self):
        self.assertEqual(json_safe([[Decimal('52000.00'), Decimal('1.50')]]), [[52000, 1.5]])

    def test_dates_become_iso_strings(self):
        rows = [[dt.date(2022, 1, 10), dt.datetime(2022, 1, 10, 9, 30), dt.time(9, 30)]]
        self.assertEqual(json_safe(rows), [['2022-01-10', '2022-01-10T09:30:00', '09:30:00']])

    def test_bytes_become_hex_and_unknown_become_text(self):
        class Odd:
            def __str__(self):
                return 'odd'
        self.assertEqual(json_safe({'b': b'\x01\xff', 'o': Odd()}), {'b': '01ff', 'o': 'odd'})

    def test_plain_values_are_untouched(self):
        self.assertEqual(json_safe([None, True, 3, 2.5, 'x']), [None, True, 3, 2.5, 'x'])

    def test_non_finite_numbers_become_text(self):
        # PostgreSQL NUMERIC allows NaN and Infinity; jsonb does not.
        self.assertEqual(json_safe([Decimal('NaN'), Decimal('Infinity'), float('inf'), float('nan')]),
                         ['NaN', 'Infinity', 'inf', 'nan'])

    def test_result_is_json_serializable(self):
        payload = json_safe({'rows': [[Decimal('1'), dt.date(2020, 5, 5), None, True, 'x']]})
        json.dumps(payload)   # must not raise
