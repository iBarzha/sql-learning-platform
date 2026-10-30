"""Mutation-based validation of an exercise's datasets.

Lightweight take on the XData idea: instead of solving constraints to synthesize data,
generate the mistakes students actually make (wrong join type, `>` for `>=`, dropped
DISTINCT, dropped WHERE condition...) as mutants of the reference query, and report
which of them the instructor's datasets fail to distinguish from the correct answer.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Optional, Sequence

from sqlglot import exp

from . import compare as cmp
from .compose import dialect_for, nondeterminism_warnings, parse_query
from .criteria import prepare_rows as _prepare_rows
from .types import CheckDataset, Execution, PURPOSE_REFERENCE, RunFn


@dataclass
class Mutant:
    kind: str
    description: str
    sql: str


@dataclass
class ValidationReport:
    mutants_total: int
    surviving: list[Mutant] = field(default_factory=list)
    reference_empty_on: list[str] = field(default_factory=list)
    reference_errors: dict[str, str] = field(default_factory=dict)
    checked: int = 0
    truncated: bool = False
    # Problems with the reference or the exercise setup that the mutants cannot show.
    warnings: list[str] = field(default_factory=list)

    @property
    def killed(self) -> int:
        return self.checked - len(self.surviving)


MAX_MUTANTS = 25
DEFAULT_BUDGET_SECONDS = 30.0

MSG_NO_HIDDEN_DATASETS = ('У вправи немає прихованих наборів: відповідь, що формально читає '
                          'таблицю, але містить готові значення, пройде перевірку.')


_COMPARISON_SWAPS = {
    exp.GT: (exp.GTE, '`>` замінено на `>=`'),
    exp.GTE: (exp.GT, '`>=` замінено на `>`'),
    exp.LT: (exp.LTE, '`<` замінено на `<=`'),
    exp.LTE: (exp.LT, '`<=` замінено на `<`'),
    exp.EQ: (exp.NEQ, '`=` замінено на `<>`'),
}

_AGGREGATE_SWAPS = {
    exp.Sum: (exp.Avg, 'SUM замінено на AVG'),
    exp.Avg: (exp.Sum, 'AVG замінено на SUM'),
    exp.Max: (exp.Min, 'MAX замінено на MIN'),
    exp.Min: (exp.Max, 'MIN замінено на MAX'),
}


def generate_mutants(reference_sql: str, db_type: str) -> list[Mutant]:
    dialect = dialect_for(db_type)
    root = parse_query(reference_sql, dialect)
    seen = {root.sql(dialect=dialect)}
    out: list[Mutant] = []

    def emit(kind: str, description: str, tree: exp.Expression) -> None:
        sql = tree.sql(dialect=dialect)
        if sql not in seen:
            seen.add(sql)
            out.append(Mutant(kind, description, sql))

    for index, join in enumerate(root.find_all(exp.Join)):
        side = (join.side or '').upper()
        tree = root.copy()
        target = list(tree.find_all(exp.Join))[index]
        if side == 'LEFT':
            target.set('side', None)
            target.set('kind', None)
            emit('join_type', 'LEFT JOIN замінено на INNER JOIN', tree)
        elif side in ('', 'INNER'):
            target.set('side', 'LEFT')
            target.set('kind', None)
            emit('join_type', 'INNER JOIN замінено на LEFT JOIN', tree)

    for node_cls, (replacement_cls, description) in _COMPARISON_SWAPS.items():
        for index, _ in enumerate(root.find_all(node_cls)):
            tree = root.copy()
            target = list(tree.find_all(node_cls))[index]
            target.replace(replacement_cls(this=target.this.copy(),
                                           expression=target.expression.copy()))
            emit('comparison', description, tree)

    for node_cls, (replacement_cls, description) in _AGGREGATE_SWAPS.items():
        for index, _ in enumerate(root.find_all(node_cls)):
            tree = root.copy()
            target = list(tree.find_all(node_cls))[index]
            target.replace(replacement_cls(this=target.this.copy()))
            emit('aggregate', description, tree)

    for index, count in enumerate(root.find_all(exp.Count)):
        if isinstance(count.this, exp.Star):
            continue
        tree = root.copy()
        target = list(tree.find_all(exp.Count))[index]
        target.set('this', exp.Star())
        emit('count', 'COUNT(стовпець) замінено на COUNT(*)', tree)

    for index, select in enumerate(root.find_all(exp.Select)):
        tree = root.copy()
        target = list(tree.find_all(exp.Select))[index]
        if target.args.get('distinct'):
            target.set('distinct', None)
            emit('distinct', 'прибрано DISTINCT', tree)
        elif not _distinct_is_noop(select):
            target.set('distinct', exp.Distinct())
            emit('distinct', 'додано зайвий DISTINCT', tree)

    for index, where in enumerate(root.find_all(exp.Where)):
        tree = root.copy()
        target = list(tree.find_all(exp.Where))[index]
        target.pop()
        emit('where', 'прибрано умову WHERE', tree)

        conjuncts = list(where.this.flatten()) if isinstance(where.this, exp.And) else []
        for c_index in range(len(conjuncts)):
            tree = root.copy()
            target = list(tree.find_all(exp.Where))[index]
            remaining = [c.copy() for i, c in enumerate(target.this.flatten()) if i != c_index]
            target.set('this', exp.and_(*remaining) if len(remaining) > 1 else remaining[0])
            emit('where', f'прибрано умову №{c_index + 1} з WHERE', tree)

        if isinstance(where.this, (exp.And, exp.Or)):
            tree = root.copy()
            target = list(tree.find_all(exp.Where))[index]
            swapped = (exp.Or if isinstance(target.this, exp.And) else exp.And)(
                this=target.this.this.copy(), expression=target.this.expression.copy())
            target.set('this', swapped)
            emit('logic', 'AND та OR поміняно місцями', tree)

    for index, _ in enumerate(root.find_all(exp.Having)):
        tree = root.copy()
        list(tree.find_all(exp.Having))[index].pop()
        emit('having', 'прибрано HAVING', tree)

    for index, _ in enumerate(root.find_all(exp.Limit)):
        tree = root.copy()
        list(tree.find_all(exp.Limit))[index].pop()
        emit('limit', 'прибрано LIMIT', tree)

    for tree, target in _copies(root, exp.Is, lambda n: isinstance(n.expression, exp.Null)):
        wrapper = target.parent if isinstance(target.parent, exp.Not) else None
        if wrapper is not None or target.args.get('negate'):
            target.set('negate', None)
            if wrapper is not None:
                wrapper.replace(target.pop())
            emit('null_test', 'IS NOT NULL замінено на IS NULL', tree)
        else:
            target.set('negate', True)
            emit('null_test', 'IS NULL замінено на IS NOT NULL', tree)

    for tree, target in _copies(root, exp.Between):
        strict = exp.and_(
            exp.GT(this=target.this.copy(), expression=target.args['low'].copy()),
            exp.LT(this=target.this.copy(), expression=target.args['high'].copy()),
        )
        if not isinstance(target.parent, (exp.Where, exp.Having, exp.And, exp.Paren)):
            strict = exp.paren(strict, copy=False)   # e.g. under NOT, keep it one condition
        target.replace(strict)
        emit('between', 'межі BETWEEN зроблено строгими', tree)

    for tree, target in _copies(root, (exp.Like, exp.ILike), _has_wildcard_pattern):
        bare = target.expression.this.replace('%', '').replace('_', '')
        if bare:
            target.set('expression', exp.Literal.string(bare))
            emit('like', 'прибрано символи підстановки з шаблону LIKE', tree)

    for group_index, group in enumerate(root.find_all(exp.Group)):
        if len(group.expressions) < 2:
            continue
        for k in range(len(group.expressions)):
            tree = root.copy()
            target = list(tree.find_all(exp.Group))[group_index]
            target.expressions[k].pop()
            emit('group_by', f'прибрано вираз №{k + 1} з GROUP BY', tree)

    for tree, target in _copies(root, exp.Join, lambda n: n.args.get('on') is not None):
        # An explicit CROSS JOIN: PostgreSQL rejects a bare JOIN without ON.
        target.set('on', None)
        target.set('side', None)
        target.set('kind', 'CROSS')
        emit('join_condition', "прибрано умову з'єднання", tree)

    for tree, target in _copies(root, exp.Not, lambda n: not isinstance(n.this, (exp.Is, exp.In))):
        target.replace(target.this.pop())
        emit('not', 'прибрано NOT', tree)

    for tree, target in _copies(root, exp.In, lambda n: not isinstance(n.parent, exp.Not)):
        target.replace(exp.Not(this=target.copy()))
        emit('in_not_in', 'IN замінено на NOT IN', tree)

    return out


def _copies(root: exp.Expression, node_types, keep=lambda node: True):
    """Yield (copy of the tree, the n-th matching node in that copy) for every match."""
    count = sum(1 for node in root.find_all(node_types) if keep(node))
    for index in range(count):
        tree = root.copy()
        yield tree, [node for node in tree.find_all(node_types) if keep(node)][index]


def _has_wildcard_pattern(node: exp.Expression) -> bool:
    pattern = node.expression
    return (isinstance(pattern, exp.Literal) and pattern.is_string
            and ('%' in pattern.this or '_' in pattern.this))


def _distinct_is_noop(select: exp.Select) -> bool:
    """DISTINCT cannot change a result that is already one row per group.

    Grouped queries and bare aggregates (`SELECT COUNT(*) FROM t`) never repeat rows,
    so the "added DISTINCT" mutant would be equivalent to the reference and could only
    show up as a false "not caught" in the report.
    """
    if select.args.get('group'):
        return True
    expressions = select.expressions or []
    return bool(expressions) and all(
        isinstance(e.unalias(), exp.AggFunc) for e in expressions
    )


def validate_datasets(
    reference_sql: str,
    datasets: Sequence[CheckDataset],
    run: RunFn,
    db_type: str,
    mutants: Optional[list[Mutant]] = None,
    *,
    max_mutants: int = MAX_MUTANTS,
    budget_seconds: float = DEFAULT_BUDGET_SECONDS,
) -> ValidationReport:
    """Report the mutants no dataset can tell apart from the reference.

    Every mutant costs one reseed per dataset, so the work is capped both by count
    and by wall-clock time; `truncated` says the report is partial.
    """
    mutants = mutants if mutants is not None else generate_mutants(reference_sql, db_type)
    report = ValidationReport(mutants_total=len(mutants))
    report.warnings = nondeterminism_warnings(reference_sql, db_type)
    if len(datasets) < 2:
        report.warnings.append(MSG_NO_HIDDEN_DATASETS)
    started = time.monotonic()

    reference_by_dataset: dict[str, Execution] = {}
    for ds in datasets:
        result = run(reference_sql, ds, PURPOSE_REFERENCE)
        reference_by_dataset[ds.name] = result
        if not result.success:
            report.reference_errors[ds.name] = result.error
        elif not result.rows:
            report.reference_empty_on.append(ds.name)

    for mutant in mutants[:max_mutants]:
        if time.monotonic() - started > budget_seconds:
            break
        report.checked += 1
        if not _is_killed(mutant, datasets, reference_by_dataset, run, db_type):
            report.surviving.append(mutant)

    report.truncated = report.checked < len(mutants)
    return report


def _is_killed(mutant, datasets, reference_by_dataset, run, db_type) -> bool:
    for ds in datasets:
        reference = reference_by_dataset[ds.name]
        if not reference.success:
            continue
        outcome = run(mutant.sql, ds, 'mutant')
        if not outcome.success:
            return True
        diff = cmp.compare(
            outcome.columns, _prepare_rows(db_type, outcome.rows),
            reference.columns, _prepare_rows(db_type, reference.rows),
        )
        if not diff.equal:
            return True
    return False
