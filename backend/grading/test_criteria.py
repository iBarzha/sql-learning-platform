"""Criteria registry: applicability, defaults, config resolution, description."""

import unittest

from grading import criteria
from grading.service import CheckDataset, GradingTask

SCHEMA = 'CREATE TABLE t (a INTEGER, b TEXT);'
PRIMARY = CheckDataset('основний', SCHEMA, "INSERT INTO t VALUES (1,'x'),(2,'y');")
HIDDEN = CheckDataset('межа', SCHEMA, "INSERT INTO t VALUES (1,'x'),(2,'y'),(3,'z');",
                      targets='третій рядок')


def task(reference='SELECT a, b FROM t', db_type='sqlite', **kw):
    return GradingTask(db_type=db_type, reference_query=reference, primary=PRIMARY, **kw)


class KindTests(unittest.TestCase):
    def test_select_reference_is_select_kind(self):
        self.assertEqual(criteria.task_kind(task()), criteria.KIND_SELECT)

    def test_dml_reference_is_dml_kind(self):
        self.assertEqual(criteria.task_kind(task('UPDATE t SET b = 1')), criteria.KIND_DML)

    def test_nosql_databases_are_nosql_kind(self):
        self.assertEqual(criteria.task_kind(task('db.t.find({})', db_type='mongodb')),
                         criteria.KIND_NOSQL)


class ApplicabilityTests(unittest.TestCase):
    def test_select_without_order_by(self):
        self.assertEqual(criteria.applicable_ids(task()),
                         ['execution', 'columns', 'column_names', 'complete', 'precise',
                          'reads_data'])

    def test_order_requires_order_by_in_reference(self):
        self.assertIn('order', criteria.applicable_ids(task('SELECT a FROM t ORDER BY a')))

    def test_legacy_order_matters_flag_enables_order(self):
        self.assertIn('order', criteria.applicable_ids(task(order_matters=True)))

    def test_constant_reference_has_no_reads_data(self):
        self.assertNotIn('reads_data', criteria.applicable_ids(task('SELECT 2 + 2')))

    def test_dml_kind(self):
        self.assertEqual(criteria.applicable_ids(task('DELETE FROM t')), ['execution', 'state'])

    def test_nosql_kind(self):
        self.assertEqual(criteria.applicable_ids(task('db.t.find({})', db_type='mongodb')),
                         ['execution', 'columns', 'complete', 'precise', 'order'])
        self.assertEqual(criteria.default_enabled(task('db.t.find({})', db_type='mongodb')),
                         ['execution', 'columns', 'complete', 'precise'])

    def test_no_reference_and_no_snapshot(self):
        self.assertEqual(criteria.applicable_ids(task('')), ['execution', 'reads_data'])

    def test_snapshot_counts_as_reference(self):
        t = task('', expected_result={'columns': ['a'], 'rows': [[1]]})
        self.assertEqual(criteria.applicable_ids(t),
                         ['execution', 'columns', 'column_names', 'complete', 'precise',
                          'reads_data'])


class DefaultTests(unittest.TestCase):
    def test_defaults_enable_everything_but_column_names(self):
        self.assertEqual(criteria.default_enabled(task('SELECT a FROM t ORDER BY a')),
                         ['execution', 'columns', 'complete', 'precise', 'order', 'reads_data'])

    def test_empty_config_resolves_to_defaults_with_threshold_all(self):
        enabled, threshold = criteria.resolve_config(task(), {})
        self.assertEqual(enabled, criteria.default_enabled(task()))
        self.assertEqual(threshold, 0)

    def test_execution_is_always_included(self):
        enabled, _ = criteria.resolve_config(task(), {'enabled': ['complete'], 'threshold': 1})
        self.assertEqual(enabled, ['execution', 'complete'])

    def test_unknown_and_inapplicable_ids_are_dropped_at_grading_time(self):
        enabled, _ = criteria.resolve_config(task(), {'enabled': ['bogus', 'order', 'precise']})
        self.assertEqual(enabled, ['execution', 'precise'])

    def test_invalid_threshold_becomes_zero(self):
        self.assertEqual(criteria.resolve_config(task(), {'threshold': 'x'})[1], 0)
        self.assertEqual(criteria.resolve_config(task(), {'threshold': -3})[1], 0)


class DerivedTests(unittest.TestCase):
    def test_datasets_and_keywords_become_criteria(self):
        t = task(hidden=[HIDDEN], required_keywords=['JOIN'], forbidden_keywords=['SUBQUERY'])
        self.assertEqual(criteria.derived_specs(t), [
            ('dataset:1', 'Контрольний набір №1'),
            ('require:JOIN', 'Використано JOIN'),
            ('forbid:SUBQUERY', 'Не використано SUBQUERY'),
        ])

    def test_datasets_need_a_reference_query(self):
        self.assertEqual(criteria.derived_specs(task('', hidden=[HIDDEN])), [])

    def test_blank_keywords_are_ignored(self):
        self.assertEqual(criteria.derived_specs(task(required_keywords=['', '  '])), [])


class DescribeTests(unittest.TestCase):
    def test_describe_lists_names_total_and_effective_threshold(self):
        t = task(hidden=[HIDDEN], required_keywords=['WHERE'])
        d = criteria.describe(t, {'enabled': ['execution', 'complete', 'precise'], 'threshold': 4})
        self.assertEqual([c['id'] for c in d['criteria']],
                         ['execution', 'complete', 'precise', 'dataset:1', 'require:WHERE'])
        self.assertEqual(d['total'], 5)
        self.assertEqual(d['threshold'], 4)

    def test_threshold_zero_or_too_big_means_all(self):
        zero = criteria.describe(task(), {'threshold': 0})
        big = criteria.describe(task(), {'threshold': 99})
        self.assertEqual(zero['threshold'], zero['total'])
        self.assertEqual(big['threshold'], big['total'])


class ValidateConfigTests(unittest.TestCase):
    def test_valid_config_is_normalized(self):
        cleaned = criteria.validate_config(task(), {'enabled': ['precise', 'complete'],
                                                    'threshold': 2})
        self.assertEqual(cleaned, {'enabled': ['execution', 'complete', 'precise'], 'threshold': 2})

    def test_unknown_id_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'Невідомий критерій'):
            criteria.validate_config(task(), {'enabled': ['magic']})

    def test_order_without_order_by_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'ORDER BY'):
            criteria.validate_config(task(), {'enabled': ['order']})

    def test_state_on_select_task_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'не застосовний'):
            criteria.validate_config(task(), {'enabled': ['state']})

    def test_threshold_must_be_a_non_negative_integer(self):
        with self.assertRaisesRegex(ValueError, 'Поріг'):
            criteria.validate_config(task(), {'threshold': -1})
        with self.assertRaisesRegex(ValueError, 'Поріг'):
            criteria.validate_config(task(), {'threshold': True})

    def test_none_and_empty_are_valid(self):
        self.assertEqual(criteria.validate_config(task(), None), {})
        self.assertEqual(criteria.validate_config(task(), {}), {})


class CatalogTests(unittest.TestCase):
    def test_catalog_payload_has_ids_names_kinds(self):
        payload = criteria.catalog_payload()
        self.assertEqual([c['id'] for c in payload],
                         ['execution', 'columns', 'column_names', 'complete', 'precise',
                          'order', 'reads_data', 'state'])
        self.assertEqual(payload[0]['kinds'], ['select', 'dml', 'nosql'])
        self.assertTrue(all(c['name'] and c['description'] for c in payload))


class ReviewFixTests(unittest.TestCase):
    """Regressions from the whole-branch review."""

    def test_empty_enabled_list_means_defaults_not_execution_only(self):
        # The form sends {"enabled": [], "threshold": 0} for an untouched exercise.
        self.assertEqual(criteria.validate_config(task(), {'enabled': [], 'threshold': 0}), {})
        cleaned = criteria.validate_config(task(), {'enabled': [], 'threshold': 2})
        self.assertEqual(cleaned, {'enabled': [], 'threshold': 2})
        enabled, threshold = criteria.resolve_config(task(), cleaned)
        self.assertEqual(enabled, criteria.default_enabled(task()))
        self.assertEqual(threshold, 2)

    def test_dml_tasks_have_no_dataset_criteria(self):
        t = task('DELETE FROM t', hidden=[HIDDEN], required_keywords=['WHERE'])
        self.assertEqual(criteria.derived_specs(t), [('require:WHERE', 'Використано WHERE')])

    def test_nosql_defaults_exclude_order_unless_order_matters(self):
        plain = task('db.t.find({})', db_type='mongodb')
        self.assertNotIn('order', criteria.default_enabled(plain))
        self.assertIn('order', criteria.applicable_ids(plain))
        ordered = task('db.t.find({}).sort({a: 1})', db_type='mongodb', order_matters=True)
        self.assertIn('order', criteria.default_enabled(ordered))

    def test_normalize_config_drops_ids_that_no_longer_apply(self):
        cleaned = criteria.normalize_config(task(), {'enabled': ['order', 'precise'],
                                                     'threshold': 3})
        self.assertEqual(cleaned, {'enabled': ['execution', 'precise'], 'threshold': 3})
