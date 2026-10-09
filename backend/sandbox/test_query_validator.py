"""Unit tests for the SQL security validator."""

import unittest

from sandbox.query_validator import QueryBlockedError, validate_sql


class LegitimateQueriesPassTests(unittest.TestCase):
    def assertAllowed(self, sql):
        try:
            validate_sql(sql)
        except QueryBlockedError as err:
            self.fail(f'blocked legitimate query {sql!r}: {err.message}')

    def test_plain_select(self):
        self.assertAllowed('SELECT id, name FROM users WHERE age > 18')

    def test_surname_grant_in_a_literal(self):
        self.assertAllowed("SELECT * FROM users WHERE last_name = 'Grant'")

    def test_use_inside_a_literal(self):
        self.assertAllowed("SELECT 'use case' AS note FROM t")

    def test_keyword_inside_a_literal_with_escaped_quote(self):
        self.assertAllowed("SELECT 'it''s a grant' FROM t")

    def test_union_is_allowed(self):
        self.assertAllowed('SELECT name FROM a UNION SELECT name FROM b')

    def test_union_all_is_allowed(self):
        self.assertAllowed('SELECT n FROM a UNION ALL SELECT n FROM b')

    def test_except_all_wrapper_used_by_grading(self):
        self.assertAllowed('(SELECT a FROM t1 EXCEPT ALL SELECT a FROM t2) '
                           'UNION ALL (SELECT a FROM t2 EXCEPT ALL SELECT a FROM t1)')

    def test_dangerous_word_inside_a_comment_is_ignored(self):
        self.assertAllowed('SELECT 1 -- pg_shadow')

    def test_dangerous_word_inside_a_block_comment_is_ignored(self):
        self.assertAllowed('SELECT 1 /* drop database x */')


class DangerousQueriesAreBlockedTests(unittest.TestCase):
    def assertBlocked(self, sql):
        with self.assertRaises(QueryBlockedError):
            validate_sql(sql)

    def test_system_catalog(self):
        self.assertBlocked('SELECT * FROM pg_shadow')

    def test_system_catalog_as_quoted_identifier(self):
        self.assertBlocked('SELECT * FROM "pg_shadow"')

    def test_union_into_system_catalog_is_still_blocked(self):
        self.assertBlocked('SELECT 1 UNION SELECT usename FROM pg_shadow')

    def test_grant_statement(self):
        self.assertBlocked('GRANT ALL ON users TO public')

    def test_drop_database(self):
        self.assertBlocked('DROP DATABASE sandbox')

    def test_file_read(self):
        self.assertBlocked("SELECT pg_read_file('/etc/passwd')")

    def test_trailing_comment_does_not_disarm_a_rule(self):
        self.assertBlocked('SELECT * FROM pg_shadow /* just looking */')

    def test_literal_does_not_swallow_the_rest_of_the_query(self):
        # An unterminated-looking literal must not hide executable SQL after it.
        self.assertBlocked("SELECT 'a' , pg_shadow.usename FROM pg_shadow")


if __name__ == '__main__':
    unittest.main()
