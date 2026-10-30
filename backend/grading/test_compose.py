"""Unit tests for AST parsing, safe composition and structural analysis."""

import unittest

import sqlglot

from grading.compose import (
    QueryShapeError,
    build_symmetric_difference,
    classify_statement,
    constructs,
    dialect_for,
    has_order_by,
    is_constant_query,
    parse_query,
    referenced_tables,
    strip_order,
    supports_except_all,
    uses_only_unrelated_tables,
)

PG = 'postgres'


class ParseTests(unittest.TestCase):
    def test_simple_select_parses(self):
        self.assertIsNotNone(parse_query('SELECT id FROM users', PG))

    def test_trailing_semicolon_is_one_statement(self):
        self.assertIsNotNone(parse_query('SELECT id FROM users;', PG))

    def test_cte_parses(self):
        self.assertIsNotNone(
            parse_query('WITH t AS (SELECT 1 AS a) SELECT a FROM t', PG))

    def test_set_operation_parses(self):
        self.assertIsNotNone(
            parse_query('SELECT a FROM x UNION ALL SELECT a FROM y', PG))

    def test_empty_query_is_rejected(self):
        with self.assertRaises(QueryShapeError):
            parse_query('   ', PG)

    def test_two_statements_are_rejected(self):
        with self.assertRaises(QueryShapeError):
            parse_query('SELECT 1; SELECT 2', PG)

    def test_statement_injection_is_rejected(self):
        with self.assertRaises(QueryShapeError):
            parse_query('SELECT id FROM users; DROP TABLE users', PG)

    def test_insert_is_rejected(self):
        with self.assertRaises(QueryShapeError):
            parse_query("INSERT INTO users VALUES (1)", PG)

    def test_update_is_rejected(self):
        with self.assertRaises(QueryShapeError):
            parse_query('UPDATE users SET name = 1', PG)

    def test_delete_is_rejected(self):
        with self.assertRaises(QueryShapeError):
            parse_query('DELETE FROM users', PG)

    def test_drop_is_rejected(self):
        with self.assertRaises(QueryShapeError):
            parse_query('DROP TABLE users', PG)

    def test_unbalanced_paren_is_rejected(self):
        with self.assertRaises(QueryShapeError):
            parse_query('SELECT id FROM users)', PG)


class OrderTests(unittest.TestCase):
    def test_order_by_is_detected(self):
        self.assertTrue(has_order_by(parse_query('SELECT a FROM t ORDER BY a', PG)))

    def test_absent_order_by_is_detected(self):
        self.assertFalse(has_order_by(parse_query('SELECT a FROM t', PG)))

    def test_order_by_inside_subquery_is_not_top_level(self):
        node = parse_query('SELECT a FROM (SELECT a FROM t ORDER BY a) s', PG)
        self.assertFalse(has_order_by(node))

    def test_strip_order_removes_it(self):
        node = parse_query('SELECT a FROM t ORDER BY a', PG)
        self.assertFalse(has_order_by(strip_order(node)))

    def test_strip_order_does_not_mutate_original(self):
        node = parse_query('SELECT a FROM t ORDER BY a', PG)
        strip_order(node)
        self.assertTrue(has_order_by(node))


class SymmetricDifferenceTests(unittest.TestCase):
    def build(self, student='SELECT a FROM t', reference='SELECT b FROM t', db='postgresql'):
        return build_symmetric_difference(student, reference, db)

    def test_uses_except_all_not_except(self):
        sql = self.build()
        self.assertIn('EXCEPT ALL', sql)

    def test_uses_union_all(self):
        self.assertIn('UNION ALL', self.build())

    def test_both_directions_are_present(self):
        self.assertEqual(self.build().count('EXCEPT ALL'), 2)

    def test_order_by_is_dropped(self):
        sql = self.build(student='SELECT a FROM t ORDER BY a')
        self.assertNotIn('ORDER BY', sql)

    def test_result_is_valid_sql(self):
        sql = self.build()
        self.assertIsNotNone(sqlglot.parse_one(sql, read=PG))

    def test_student_text_cannot_escape_the_wrapper(self):
        with self.assertRaises(QueryShapeError):
            self.build(student='SELECT a FROM t; DROP TABLE t')

    def test_sqlite_is_refused_because_it_lacks_except_all(self):
        with self.assertRaises(QueryShapeError):
            self.build(db='sqlite')

    def test_aliases_do_not_change_the_shape(self):
        sql = self.build(student='SELECT a AS x FROM t', reference='SELECT a FROM t')
        self.assertIsNotNone(sqlglot.parse_one(sql, read=PG))

    def test_every_operand_is_parenthesized(self):
        sql = self.build()
        self.assertEqual(sql.count('('), 6)
        self.assertTrue(sql.startswith('(('))

    def test_union_in_student_answer_keeps_its_own_grouping(self):
        sql = self.build(student='SELECT a FROM x UNION SELECT a FROM y')
        self.assertIn('((SELECT a FROM x UNION SELECT a FROM y) EXCEPT ALL (SELECT b FROM t))', sql)

    def test_limit_in_student_answer_stays_inside_its_operand(self):
        sql = self.build(student='SELECT a FROM t ORDER BY a LIMIT 5')
        self.assertIn('(SELECT a FROM t ORDER BY a LIMIT 5)', sql)

    def test_order_by_is_kept_when_limit_depends_on_it(self):
        node = parse_query('SELECT a FROM t ORDER BY a LIMIT 3', PG)
        self.assertTrue(has_order_by(strip_order(node)))


class ClassifyTests(unittest.TestCase):
    def test_select(self):
        self.assertEqual(classify_statement('SELECT 1 FROM t', PG), 'select')

    def test_dml(self):
        self.assertEqual(classify_statement('UPDATE t SET a = 1', PG), 'dml')
        self.assertEqual(classify_statement('DELETE FROM t', PG), 'dml')
        self.assertEqual(classify_statement('INSERT INTO t VALUES (1)', PG), 'dml')
        self.assertEqual(classify_statement('CREATE TABLE x (a INT)', PG), 'dml')

    def test_multiple(self):
        self.assertEqual(classify_statement('SELECT 1; SELECT 2', PG), 'multiple')

    def test_invalid_and_empty(self):
        self.assertEqual(classify_statement('SELEC 1 FROM', PG), 'invalid')
        self.assertEqual(classify_statement('   ', PG), 'empty')


class CapabilityTests(unittest.TestCase):
    def test_postgres_supports_except_all(self):
        self.assertTrue(supports_except_all('postgresql'))

    def test_mariadb_supports_except_all(self):
        self.assertTrue(supports_except_all('mariadb'))

    def test_sqlite_does_not(self):
        self.assertFalse(supports_except_all('sqlite'))

    def test_mongodb_does_not(self):
        self.assertFalse(supports_except_all('mongodb'))

    def test_dialect_mapping(self):
        self.assertEqual(dialect_for('postgresql'), 'postgres')
        self.assertEqual(dialect_for('mariadb'), 'mysql')
        self.assertIsNone(dialect_for('redis'))


class HardcodeDetectionTests(unittest.TestCase):
    def test_constant_select_is_flagged(self):
        self.assertTrue(is_constant_query(parse_query("SELECT 'Kyiv' AS city", PG)))

    def test_constant_union_chain_is_flagged(self):
        node = parse_query("SELECT 'a', 1 UNION ALL SELECT 'b', 2", PG)
        self.assertTrue(is_constant_query(node))

    def test_real_query_is_not_flagged(self):
        self.assertFalse(is_constant_query(parse_query('SELECT a FROM t', PG)))

    def test_cte_over_constants_is_still_constant(self):
        node = parse_query('WITH c AS (SELECT 1 AS a) SELECT a FROM c', PG)
        self.assertTrue(is_constant_query(node))

    def test_cte_over_real_table_is_not_constant(self):
        node = parse_query('WITH c AS (SELECT a FROM t) SELECT a FROM c', PG)
        self.assertFalse(is_constant_query(node))

    def test_table_valued_function_reads_data(self):
        node = parse_query('SELECT g FROM generate_series(1, 1500) AS g', PG)
        self.assertFalse(is_constant_query(node))

    def test_unnest_reads_data(self):
        node = parse_query('SELECT u FROM unnest(ARRAY[1, 2]) AS u', PG)
        self.assertFalse(is_constant_query(node))

    def test_values_list_is_constant(self):
        node = parse_query('SELECT x FROM (VALUES (1), (2)) AS v(x)', PG)
        self.assertTrue(is_constant_query(node))

    def test_constant_subquery_is_constant(self):
        node = parse_query('SELECT a FROM (SELECT 1 AS a) AS s', PG)
        self.assertTrue(is_constant_query(node))

    def test_subquery_over_table_is_not_constant(self):
        node = parse_query('SELECT a FROM (SELECT a FROM t) AS s', PG)
        self.assertFalse(is_constant_query(node))

    def test_join_to_a_table_reads_data(self):
        node = parse_query('SELECT 1 FROM (SELECT 1 AS a) s JOIN t ON t.a = s.a', PG)
        self.assertFalse(is_constant_query(node))

    def test_referenced_tables_are_lowercased(self):
        self.assertEqual(referenced_tables(parse_query('SELECT a FROM Users', PG)),
                         {'users'})

    def test_join_tables_are_collected(self):
        node = parse_query('SELECT 1 FROM a JOIN b ON a.id = b.id', PG)
        self.assertEqual(referenced_tables(node), {'a', 'b'})

    def test_querying_unrelated_tables_is_detected(self):
        node = parse_query('SELECT a FROM other', PG)
        self.assertTrue(uses_only_unrelated_tables(node, ['employees']))

    def test_querying_expected_table_is_fine(self):
        node = parse_query('SELECT a FROM employees', PG)
        self.assertFalse(uses_only_unrelated_tables(node, ['employees']))


class ConstructTests(unittest.TestCase):
    def features(self, sql):
        return constructs(parse_query(sql, PG))

    def test_left_join_is_labelled(self):
        found = self.features('SELECT 1 FROM a LEFT JOIN b ON a.id = b.id')
        self.assertIn('LEFT JOIN', found)
        self.assertIn('JOIN', found)

    def test_inner_join_is_labelled(self):
        self.assertIn('INNER JOIN',
                      self.features('SELECT 1 FROM a JOIN b ON a.id = b.id'))

    def test_left_join_is_not_reported_as_inner(self):
        self.assertNotIn('INNER JOIN',
                         self.features('SELECT 1 FROM a LEFT JOIN b ON a.id = b.id'))

    def test_group_by_is_detected(self):
        self.assertIn('GROUP BY', self.features('SELECT a FROM t GROUP BY a'))

    def test_having_is_detected(self):
        self.assertIn('HAVING',
                      self.features('SELECT a FROM t GROUP BY a HAVING COUNT(*) > 1'))

    def test_distinct_is_detected(self):
        self.assertIn('DISTINCT', self.features('SELECT DISTINCT a FROM t'))

    def test_distinct_absent_when_not_used(self):
        self.assertNotIn('DISTINCT', self.features('SELECT a FROM t'))

    def test_aggregate_is_detected(self):
        found = self.features('SELECT COUNT(*) FROM t')
        self.assertIn('COUNT', found)
        self.assertIn('AGGREGATE', found)

    def test_subquery_is_detected(self):
        self.assertIn('SUBQUERY',
                      self.features('SELECT a FROM t WHERE a IN (SELECT b FROM u)'))

    def test_exists_is_detected(self):
        self.assertIn('EXISTS',
                      self.features('SELECT a FROM t WHERE EXISTS (SELECT 1 FROM u)'))

    def test_window_function_is_detected(self):
        self.assertIn('WINDOW',
                      self.features('SELECT ROW_NUMBER() OVER (ORDER BY a) FROM t'))

    # These are the reason the checks moved off regular expressions.
    def test_keyword_inside_a_string_literal_does_not_count(self):
        self.assertNotIn('GROUP BY', self.features("SELECT 'GROUP BY' AS note FROM t"))

    def test_join_inside_a_string_literal_does_not_count(self):
        self.assertNotIn('JOIN', self.features("SELECT 'INNER JOIN' AS note FROM t"))

    def test_distinct_inside_a_string_literal_does_not_count(self):
        self.assertNotIn('DISTINCT', self.features("SELECT 'DISTINCT' AS note FROM t"))

    def test_keyword_as_a_column_name_does_not_count(self):
        self.assertNotIn('JOIN', self.features('SELECT t.join_date FROM t'))


if __name__ == '__main__':
    unittest.main()


class ConstructsInComparisonsTests(unittest.TestCase):
    def test_subquery_inside_a_comparison_counts(self):
        from grading.compose import constructs, parse_query
        node = parse_query('SELECT cnum FROM Customers o '
                           'WHERE rating = (SELECT MAX(rating) FROM Customers i WHERE i.city = o.city)',
                           'postgres')
        self.assertIn('SUBQUERY', constructs(node))

    def test_subquery_after_any_and_all_counts(self):
        from grading.compose import constructs, parse_query
        node = parse_query('SELECT * FROM Orders WHERE amt > ALL (SELECT amt FROM Orders)', 'postgres')
        self.assertIn('SUBQUERY', constructs(node))
        self.assertIn('ALL', constructs(node))

    def test_derived_table_is_not_a_predicate_subquery(self):
        from grading.compose import constructs, parse_query
        node = parse_query('SELECT * FROM (SELECT snum FROM Orders) t', 'postgres')
        self.assertNotIn('SUBQUERY', constructs(node))


class OrderKeyPositionsTests(unittest.TestCase):
    def keys(self, sql):
        from grading.compose import order_key_positions
        return order_key_positions(parse_query(sql, PG))

    def test_ordinal(self):
        self.assertEqual(self.keys('SELECT snum, amt FROM Orders ORDER BY 2 DESC'), [1])

    def test_ordinal_out_of_range_is_unmappable(self):
        self.assertIsNone(self.keys('SELECT snum, amt FROM Orders ORDER BY 3'))

    def test_alias(self):
        self.assertEqual(
            self.keys('SELECT snum, SUM(amt) AS total FROM Orders GROUP BY snum ORDER BY total'),
            [1])

    def test_bare_column_with_table_qualifier(self):
        self.assertEqual(
            self.keys('SELECT c.cname, rating FROM Customers c ORDER BY c.rating DESC, 1'),
            [1, 0])

    def test_expression(self):
        self.assertEqual(self.keys('SELECT onum, amt * .12 FROM Orders ORDER BY amt * .12'), [1])

    def test_star_gives_none(self):
        self.assertIsNone(self.keys('SELECT * FROM Orders ORDER BY amt'))

    def test_unselected_column_gives_none(self):
        self.assertIsNone(self.keys('SELECT name FROM employees ORDER BY salary'))

    def test_no_order_by_gives_none(self):
        self.assertIsNone(self.keys('SELECT name FROM employees'))

    def test_bare_name_resolves_to_the_output_alias_first(self):
        self.assertEqual(self.keys('SELECT b AS a, a AS b FROM t ORDER BY a'), [0])

    def test_self_join_maps_the_qualified_column_exactly(self):
        self.assertEqual(
            self.keys('SELECT a.city, b.city FROM Customers a JOIN Customers b ON a.cnum < b.cnum '
                      'ORDER BY b.city'),
            [1])

    def test_set_operation_uses_first_operand_select_list(self):
        self.assertEqual(
            self.keys('SELECT cname, city FROM Customers UNION SELECT sname, city FROM Salespeople '
                      'ORDER BY city'),
            [1])


class NondeterminismWarningsTests(unittest.TestCase):
    LIMIT = 'LIMIT без ORDER BY: набір рядків може відрізнятися між запусками.'

    def warnings(self, sql):
        from grading.compose import nondeterminism_warnings
        return nondeterminism_warnings(sql, 'postgresql')

    def test_limit_without_order_by(self):
        self.assertEqual(self.warnings('SELECT name FROM employees LIMIT 3'), [self.LIMIT])

    def test_offset_without_order_by(self):
        self.assertEqual(self.warnings('SELECT name FROM employees OFFSET 3'), [self.LIMIT])

    def test_fetch_without_order_by(self):
        self.assertEqual(self.warnings('SELECT name FROM employees FETCH FIRST 3 ROWS ONLY'),
                         [self.LIMIT])

    def test_limit_with_order_by_is_clean(self):
        self.assertEqual(self.warnings('SELECT name FROM employees ORDER BY name LIMIT 3'), [])

    def test_outer_order_by_of_a_set_operation_counts_for_its_operands(self):
        self.assertEqual(self.warnings(
            '(SELECT name FROM a LIMIT 1) UNION (SELECT name FROM b LIMIT 1) ORDER BY 1'), [])

    def test_limit_is_reported_once(self):
        self.assertEqual(self.warnings(
            'SELECT name FROM a WHERE id IN (SELECT id FROM b LIMIT 2) LIMIT 1'), [self.LIMIT])

    def test_nondeterministic_function_once_per_name(self):
        self.assertEqual(self.warnings('SELECT RANDOM(), RANDOM(), newid() FROM employees'), [
            'Функція rand() дає різний результат при кожному запуску; '
            'еталон може не збігтися сам із собою.',
            'Функція newid() дає різний результат при кожному запуску; '
            'еталон може не збігтися сам із собою.',
        ])

    def test_current_timestamp_node_class_is_recognised(self):
        self.assertEqual(len(self.warnings('SELECT name, CURRENT_TIMESTAMP FROM employees')), 1)

    def test_deterministic_query_is_clean(self):
        self.assertEqual(self.warnings('SELECT name, UPPER(name) FROM employees'), [])

    def test_unparseable_sql_gives_no_warnings(self):
        self.assertEqual(self.warnings('SELEC nope ((('), [])
