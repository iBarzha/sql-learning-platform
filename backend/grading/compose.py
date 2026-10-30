"""AST-level handling of student queries.

Every transformation goes through sqlglot and is rendered back from the tree. The
student's SQL text is never concatenated into a wrapper query - that would let a
crafted submission break out of the comparison and run something else.
"""

from __future__ import annotations

import re
from typing import Iterable, Optional

import sqlglot
from sqlglot import exp

DIALECT_BY_DB_TYPE = {
    'postgresql': 'postgres',
    'mariadb': 'mysql',
    'mysql': 'mysql',
    'sqlite': 'sqlite',
}

# SQLite has EXCEPT but not EXCEPT ALL, so it cannot express multiset difference.
DB_TYPES_WITH_EXCEPT_ALL = frozenset({'postgresql', 'mariadb', 'mysql'})

QUERY_NODES = (exp.Select, exp.Union, exp.Except, exp.Intersect, exp.Subquery)


class QueryShapeError(ValueError):
    """The submission is not a single readable query."""


def dialect_for(db_type: str) -> Optional[str]:
    return DIALECT_BY_DB_TYPE.get(db_type)


def supports_except_all(db_type: str) -> bool:
    return db_type in DB_TYPES_WITH_EXCEPT_ALL


def parse_query(sql: str, dialect: Optional[str]) -> exp.Expression:
    """Parse exactly one SELECT-shaped statement, or raise QueryShapeError."""
    if not sql or not sql.strip():
        raise QueryShapeError('Запит порожній.')
    try:
        parsed = sqlglot.parse(sql, read=dialect)
    except Exception as err:
        raise QueryShapeError(f'Не вдалося розібрати SQL: {err}') from err

    statements = [node for node in parsed if node is not None]
    if len(statements) != 1:
        raise QueryShapeError(
            f'Очікується рівно одна інструкція, а знайдено {len(statements)}.'
        )

    node = statements[0]
    if not isinstance(node, QUERY_NODES):
        raise QueryShapeError(
            f'Очікується SELECT, а знайдено {type(node).__name__.upper()}.'
        )
    return node


def has_order_by(node: exp.Expression) -> bool:
    return node.args.get('order') is not None


def strip_order(node: exp.Expression) -> exp.Expression:
    """Drop the top-level ORDER BY; it is meaningless inside a set operation.

    Kept when LIMIT/OFFSET is present: there the ORDER BY decides *which* rows
    survive, so removing it would change the result.
    """
    clone = node.copy()
    if clone.args.get('limit') is None and clone.args.get('offset') is None:
        clone.set('order', None)
    return clone


STATEMENT_SELECT = 'select'
STATEMENT_DML = 'dml'
STATEMENT_MULTIPLE = 'multiple'
STATEMENT_INVALID = 'invalid'
STATEMENT_EMPTY = 'empty'


def classify_statement(sql: str, dialect: Optional[str]) -> str:
    """What kind of thing the text is, without executing it."""
    if not sql or not sql.strip():
        return STATEMENT_EMPTY
    try:
        parsed = sqlglot.parse(sql, read=dialect)
    except Exception:
        return STATEMENT_INVALID
    statements = [node for node in parsed if node is not None]
    if len(statements) != 1:
        return STATEMENT_MULTIPLE
    return STATEMENT_SELECT if isinstance(statements[0], QUERY_NODES) else STATEMENT_DML


def build_symmetric_difference(
    student_sql: str,
    reference_sql: str,
    db_type: str,
) -> str:
    """((student) EXCEPT ALL (reference)) UNION ALL ((reference) EXCEPT ALL (student)).

    Empty result means the two answers are identical as multisets. Every operand is
    parenthesized: set operators are left-associative with equal precedence, so an
    answer that itself contains UNION would otherwise be re-associated into a
    different expression.
    """
    if not supports_except_all(db_type):
        raise QueryShapeError(f'{db_type} не підтримує EXCEPT ALL.')

    dialect = dialect_for(db_type)
    student = strip_order(parse_query(student_sql, dialect))
    reference = strip_order(parse_query(reference_sql, dialect))

    left = exp.Except(this=exp.paren(student.copy()), expression=exp.paren(reference.copy()),
                      distinct=False)
    right = exp.Except(this=exp.paren(reference.copy()), expression=exp.paren(student.copy()),
                       distinct=False)
    return exp.Union(this=exp.paren(left), expression=exp.paren(right),
                     distinct=False).sql(dialect=dialect)


_CREATE_TABLE_RE = re.compile(
    r'\bCREATE\s+(?:TEMP(?:ORARY)?\s+)?TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?([`"\[]?[\w.]+[`"\]]?)',
    re.IGNORECASE,
)


def tables_in_schema(schema_sql: str, dialect: Optional[str]) -> list[str]:
    """Names of the tables a schema script creates, in order."""
    names: list[str] = []
    try:
        parsed = sqlglot.parse(schema_sql or '', read=dialect)
    except Exception:
        parsed = None
    if parsed:
        for node in parsed:
            if isinstance(node, exp.Create) and (node.args.get('kind') or '').upper() == 'TABLE':
                target = node.this
                table = target.this if isinstance(target, exp.Schema) else target
                if isinstance(table, exp.Table) and table.name:
                    names.append(table.name)
    if not names:
        names = [m.group(1).strip('`"[]') for m in _CREATE_TABLE_RE.finditer(schema_sql or '')]
    seen, ordered = set(), []
    for name in names:
        if name.lower() not in seen:
            seen.add(name.lower())
            ordered.append(name)
    return ordered


def created_table(node: Optional[exp.Expression]) -> Optional[str]:
    """The table or view a CREATE statement defines, if the node is one.

    A view is graded like a table: its rows after the statement are what counts.
    """
    if isinstance(node, exp.Create) and (node.args.get('kind') or '').upper() in ('TABLE', 'VIEW'):
        target = node.this
        table = target.this if isinstance(target, exp.Schema) else target
        if isinstance(table, exp.Table):
            return table.name or None
    return None


_CREATE_OBJECT_RE = re.compile(
    r'\bCREATE\s+(?:OR\s+REPLACE\s+)?(?:TEMP(?:ORARY)?\s+)?(?:TABLE|VIEW)\s+'
    r'(?:IF\s+NOT\s+EXISTS\s+)?([`"\[]?[\w.]+[`"\]]?)',
    re.IGNORECASE,
)


def created_object_name(sql: str) -> Optional[str]:
    """Table or view a CREATE statement defines, from the text alone.

    Used when sqlglot cannot parse the statement (e.g. `WITH CHECK OPTION`).
    """
    match = _CREATE_OBJECT_RE.search(sql or '')
    return match.group(1).strip('`"[]') if match else None


def parse_statement(sql: str, dialect: Optional[str]) -> Optional[exp.Expression]:
    """Parse any single statement (not just SELECT); None when it cannot be parsed."""
    try:
        parsed = [n for n in sqlglot.parse(sql or '', read=dialect) if n is not None]
    except Exception:
        return None
    return parsed[0] if len(parsed) == 1 else None


def select_all_sql(table: str, dialect: Optional[str]) -> str:
    return exp.select('*').from_(exp.to_table(table)).sql(dialect=dialect)


def referenced_tables(node: exp.Expression) -> set[str]:
    """Base tables the query reads, excluding CTE names it defines itself."""
    defined = {
        cte.alias_or_name.lower()
        for cte in node.find_all(exp.CTE)
        if cte.alias_or_name
    }
    tables = set()
    for table in node.find_all(exp.Table):
        name = table.name
        if name and name.lower() not in defined:
            tables.add(name.lower())
    return tables


def reads_data(node: exp.Expression) -> bool:
    """True when some SELECT pulls rows from a real source.

    Base tables and table-valued functions (generate_series, unnest, MariaDB's
    seq_* tables) read data; VALUES lists, constant subqueries and CTEs built only
    from those do not.
    """
    defined = {
        cte.alias_or_name.lower()
        for cte in node.find_all(exp.CTE)
        if cte.alias_or_name
    }
    for select in node.find_all(exp.Select):
        sources = []
        # sqlglot renamed the FROM arg from "from" to "from_" in v30.
        from_clause = select.args.get('from_') or select.args.get('from')
        if from_clause is not None:
            sources.append(from_clause.this)
        for join in select.args.get('joins') or []:
            sources.append(join.this)
        for source in sources:
            if isinstance(source, (exp.Subquery, exp.Values)):
                continue
            if isinstance(source, exp.Table):
                if not isinstance(source.this, exp.Identifier):
                    return True
                if source.name.lower() not in defined:
                    return True
                continue
            return True
    return False


def is_constant_query(node: exp.Expression) -> bool:
    """True when the query reads nothing - the signature of a hardcoded answer."""
    return not reads_data(node)


def uses_only_unrelated_tables(node: exp.Expression, expected: Iterable[str]) -> bool:
    expected_lower = {t.lower() for t in expected if t}
    if not expected_lower:
        return False
    return not (referenced_tables(node) & expected_lower)


_SET_WRAPPERS = (exp.Subquery, exp.Paren, exp.Union, exp.Except, exp.Intersect)


def _is_predicate_subquery(select: exp.Select, root: exp.Expression) -> bool:
    if select is root:
        return False
    parent = select.parent
    while parent is not None and isinstance(parent, _SET_WRAPPERS):
        parent = parent.parent
    return parent is not None and not isinstance(parent, (exp.From, exp.Join, exp.CTE, exp.With))


def constructs(node: exp.Expression) -> set[str]:
    """Structural features present in the query, for required/forbidden checks.

    Derived from the tree, so a keyword inside a string literal or a column name
    never counts as usage.
    """
    found: set[str] = set()

    for join in node.find_all(exp.Join):
        side = (join.side or '').upper()
        kind = (join.kind or '').upper()
        label = ' '.join(part for part in (side, kind) if part) or 'INNER'
        found.add(f'{label} JOIN')
        found.add('JOIN')

    if node.find(exp.Group):
        found.add('GROUP BY')
    if node.find(exp.Having):
        found.add('HAVING')
    if node.args.get('order') or node.find(exp.Order):
        found.add('ORDER BY')
    if node.find(exp.Where):
        found.add('WHERE')
    if node.find(exp.Limit):
        found.add('LIMIT')
    if node.find(exp.Union):
        found.add('UNION')
    if node.find(exp.Except):
        found.add('EXCEPT')
    if node.find(exp.Intersect):
        found.add('INTERSECT')
    if node.find(exp.Window):
        found.add('WINDOW')
    if node.find(exp.Case):
        found.add('CASE')

    for select in node.find_all(exp.Select):
        if select.args.get('distinct'):
            found.add('DISTINCT')

    # A nested SELECT anywhere but as a FROM/JOIN source (a derived table) or a CTE body
    # is the kind of subquery textbooks mean: in a comparison, IN, EXISTS, ANY/ALL.
    if any(_is_predicate_subquery(select, node) for select in node.find_all(exp.Select)):
        found.add('SUBQUERY')
    if node.find(exp.Exists):
        found.add('EXISTS')
    if node.find(exp.All):
        found.add('ALL')
    if node.find(exp.Any):
        found.add('ANY')

    for func in node.find_all(exp.AggFunc):
        found.add(type(func).__name__.upper())
        found.add('AGGREGATE')

    return found


_SET_OPERATIONS = (exp.Union, exp.Except, exp.Intersect)


def _output_select(node: exp.Expression) -> Optional[exp.Select]:
    """The SELECT whose list names the output columns: the left-most set operand."""
    while isinstance(node, (*_SET_OPERATIONS, exp.Subquery, exp.Paren)):
        node = node.this
    return node if isinstance(node, exp.Select) else None


def _key_position(term: exp.Expression, items: list[exp.Expression]) -> Optional[int]:
    """0-based output column an ORDER BY term sorts by, or None when it is not one."""
    if isinstance(term, exp.Literal) and not term.is_string:
        try:
            ordinal = int(term.this)
        except ValueError:
            return None
        return ordinal - 1 if 1 <= ordinal <= len(items) else None
    if isinstance(term, (exp.Column, exp.Identifier)) and not term.is_star:
        name = term.name.lower()
        for index, item in enumerate(items):
            if isinstance(item, exp.Alias) and item.alias.lower() == name:
                return index
        for index, item in enumerate(items):
            if isinstance(item, exp.Column) and item.name.lower() == name:
                return index
    text = term.sql()
    for index, item in enumerate(items):
        if item.unalias().sql() == text:
            return index
    return None


def order_key_positions(node: Optional[exp.Expression]) -> Optional[list[int]]:
    """Output column indices the outermost ORDER BY sorts by, in order.

    Rows that tie on these keys may come back in any order, so only the keys are
    compared. None means "compare whole rows": no ORDER BY, a `*` in the select list,
    or a term that is not an output column (e.g. sorting by an unselected column).
    """
    if node is None or node.args.get('order') is None:
        return None
    select = _output_select(node)
    if select is None:
        return None
    items = list(select.expressions)
    if not items or any(item.is_star for item in items):
        return None
    positions = []
    for ordered in node.args['order'].expressions:
        term = ordered.this if isinstance(ordered, exp.Ordered) else ordered
        position = _key_position(term, items)
        if position is None:
            return None
        positions.append(position)
    return positions
