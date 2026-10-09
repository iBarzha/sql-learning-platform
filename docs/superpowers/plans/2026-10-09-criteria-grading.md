# Criteria-Based Grading Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the fixed 70/15/15 rubric with instructor-selected binary criteria and a pass threshold ("достатньо N з M"); score is full or zero.

**Architecture:** A new `grading/criteria.py` holds a registry of criteria (id, name, applicability) plus one `evaluate()` that builds a lazily-computed context (executions, diff, AST, hidden-dataset verdicts, table states) and asks every selected criterion for a yes/no verdict. `service.grade()` becomes thin: evaluate, compare `passed_count >= threshold`, build feedback. Exercise/assignment models get a `criteria` JSON field; serializers validate it against the registry and expose a `criteria_summary` for students; the frontend gets a criteria editor in the lesson form and a checklist in the student pages.

**Tech Stack:** Django 6 + DRF, sqlglot 30, React 18 + TypeScript + react-hook-form + zod + TanStack Query, shadcn/ui.

**Spec:** `docs/superpowers/specs/2026-10-09-criteria-grading-design.md`

## Global Constraints

- Backend tests run with `cd backend && .venv/Scripts/python manage.py test <module> --settings=config.settings_test` (SQLite, rate limits off). Full suite must stay green (380 tests before this work).
- All user-facing grading strings are Ukrainian (as in the current `service.py`).
- Do NOT commit: the branch `feature/admin-dashboard` already carries ~86 uncommitted files and the user commits on request only. No commit steps in this plan.
- Keep existing public names importable from `grading.service` (`CheckDataset`, `Execution`, `GradingTask`, `grade`, `PURPOSE_*`, `_prepare_rows`): `mutants.py` and the test suite import them from there.
- Existing exercises with empty `criteria` must keep today's meaning of "correct" (see Task 1 defaults); only the score changes to 100/0.
- Frontend check is `cd frontend && npm run build` (runs `tsc -b`); it must pass with zero errors.
- Dev server runs with `--noreload`; restart it by hand after backend changes when doing the browser check (Task 11).

## Review Focus

1. Student query that sqlglot cannot parse but the engine runs (dialect-specific syntax): `reads_data` and keyword criteria must not fail just because the AST is missing — Task 2 test `test_unparseable_query_is_graded_by_execution_only`.
2. `criteria.threshold` larger than the number of criteria after the instructor deleted a dataset: grading must clamp to "all", not reject every answer — Task 2 test `test_threshold_above_total_means_all`.
3. Old exercise with `order_matters=True` but no ORDER BY in the reference: default config must still include `order` (legacy behaviour) — Task 1 test `test_legacy_order_matters_flag_enables_order`.
4. Student submits a correct query whose column names differ while the instructor enabled `column_names`: must fail only that criterion, `complete`/`precise` pass — Task 2 test `test_column_names_fail_alone`.
5. PostgreSQL NUMERIC/DATE columns in a stored result caused HTTP 500: Task 7 tests `test_result_with_decimal_and_dates_is_stored` and the engine test `test_numeric_and_date_columns_are_stored` guard it.

---

### Task 1: Registry, applicability, defaults, config (`grading/types.py`, `grading/criteria.py` part 1)

**Files:**
- Create: `backend/grading/types.py`
- Create: `backend/grading/criteria.py`
- Test: `backend/grading/test_criteria.py`

**Interfaces:**
- Produces `grading.types`: `CheckDataset`, `Execution`, `RunFn`, `SequenceRunFn`, `GradingTask` (new field `criteria: Optional[dict] = None`), `PURPOSE_STUDENT/REFERENCE/DIFF`, `NOSQL_TYPES`, `SELECT_TASK_TYPES`.
- Produces `grading.criteria`: `KIND_SELECT/KIND_DML/KIND_NOSQL`, `CriterionSpec`, `GENERAL`, `GENERAL_BY_ID`, `task_kind(task)`, `applicable_ids(task)`, `default_enabled(task)`, `resolve_config(task, config) -> (list[str], int)`, `derived_specs(task) -> list[tuple[str, str]]`, `describe(task, config=None) -> dict`, `validate_config(task, config) -> dict`, `catalog_payload() -> list[dict]`.

- [ ] **Step 1: Move the shared types out of `service.py`**

Create `backend/grading/types.py` with exactly the dataclasses now at the top of `service.py` (lines 55-113) plus the new `criteria` field:

```python
"""Value types shared by the grading core.

Kept free of Django so the core stays unit-testable without a database.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Optional, Sequence

NOSQL_TYPES = frozenset({'mongodb', 'redis'})
SELECT_TASK_TYPES = frozenset({'select', ''})

PURPOSE_STUDENT = 'student'
PURPOSE_REFERENCE = 'reference'
PURPOSE_DIFF = 'diff'

_TIMEOUT_MARKERS = ('timeout', 'timed out', 'max_statement_time', 'max_execution_time',
                    'interrupted')


@dataclass
class CheckDataset:
    name: str
    schema_sql: str
    seed_sql: str
    targets: str = ''


@dataclass
class Execution:
    success: bool
    columns: list[str] = field(default_factory=list)
    rows: list[list[Any]] = field(default_factory=list)
    truncated: bool = False
    affected_rows: int = 0
    error: str = ''
    execution_time_ms: int = 0

    @property
    def timed_out(self) -> bool:
        text = (self.error or '').lower()
        return not self.success and any(marker in text for marker in _TIMEOUT_MARKERS)


RunFn = Callable[[str, CheckDataset, str], Execution]
SequenceRunFn = Callable[[Sequence[str], CheckDataset, str], list[Execution]]


@dataclass
class GradingTask:
    db_type: str
    reference_query: str
    primary: CheckDataset
    hidden: list[CheckDataset] = field(default_factory=list)
    required_keywords: list[str] = field(default_factory=list)
    forbidden_keywords: list[str] = field(default_factory=list)
    order_matters: bool = False
    max_score: int = 100
    query_type: str = 'select'
    expected_result: Optional[dict] = None
    # {"enabled": [...general criterion ids...], "threshold": int}; empty = defaults
    criteria: Optional[dict] = None

    @property
    def is_select_task(self) -> bool:
        return (self.query_type or 'select').lower() in SELECT_TASK_TYPES
```

In `service.py`, delete those definitions and replace with `from .types import (CheckDataset, Execution, GradingTask, NOSQL_TYPES, PURPOSE_DIFF, PURPOSE_REFERENCE, PURPOSE_STUDENT, RunFn, SELECT_TASK_TYPES, SequenceRunFn)  # noqa: F401 - re-exported`. Run `manage.py test grading --settings=config.settings_test`: still 236 OK.

- [ ] **Step 2: Write the failing registry tests**

`backend/grading/test_criteria.py`:

```python
"""Criteria registry: applicability, defaults, config resolution, description."""

import unittest

from grading import criteria
from grading.service import CheckDataset, GradingTask

SCHEMA = 'CREATE TABLE t (a INTEGER, b TEXT);'
PRIMARY = CheckDataset('основний', SCHEMA, "INSERT INTO t VALUES (1,'x'),(2,'y');")
HIDDEN = CheckDataset('межа', SCHEMA, "INSERT INTO t VALUES (1,'x'),(2,'y'),(3,'z');", targets='третій рядок')


def task(reference='SELECT a, b FROM t', db_type='sqlite', **kw):
    return GradingTask(db_type=db_type, reference_query=reference, primary=PRIMARY, **kw)


class KindTests(unittest.TestCase):
    def test_select_reference_is_select_kind(self):
        self.assertEqual(criteria.task_kind(task()), criteria.KIND_SELECT)

    def test_dml_reference_is_dml_kind(self):
        self.assertEqual(criteria.task_kind(task('UPDATE t SET b = 1')), criteria.KIND_DML)

    def test_nosql_databases_are_nosql_kind(self):
        self.assertEqual(criteria.task_kind(task('db.t.find({})', db_type='mongodb')), criteria.KIND_NOSQL)


class ApplicabilityTests(unittest.TestCase):
    def test_select_without_order_by(self):
        self.assertEqual(criteria.applicable_ids(task()),
                         ['execution', 'columns', 'column_names', 'complete', 'precise', 'reads_data'])

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

    def test_no_reference_and_no_snapshot(self):
        self.assertEqual(criteria.applicable_ids(task('')), ['execution', 'reads_data'])

    def test_snapshot_counts_as_reference(self):
        t = task('', expected_result={'columns': ['a'], 'rows': [[1]]})
        self.assertEqual(criteria.applicable_ids(t),
                         ['execution', 'columns', 'column_names', 'complete', 'precise', 'reads_data'])


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
        self.assertEqual(criteria.describe(task(), {'threshold': 0})['threshold'],
                         criteria.describe(task(), {'threshold': 0})['total'])
        self.assertEqual(criteria.describe(task(), {'threshold': 99})['threshold'],
                         criteria.describe(task(), {'threshold': 99})['total'])


class ValidateConfigTests(unittest.TestCase):
    def test_valid_config_is_normalized(self):
        cleaned = criteria.validate_config(task(), {'enabled': ['precise', 'complete'], 'threshold': 2})
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
```

- [ ] **Step 3: Run the tests to see them fail**

Run: `cd backend && .venv/Scripts/python manage.py test grading.test_criteria --settings=config.settings_test`
Expected: ImportError (`grading.criteria` does not exist).

- [ ] **Step 4: Write `grading/criteria.py` part 1 (registry + config)**

```python
"""Binary grading criteria.

Each criterion is one yes/no question about a submission. The instructor chooses which
questions count for an exercise and how many "yes" answers are enough (`describe`);
`evaluate` (part 2 of this module) asks every selected question. Scoring is a single
comparison, passed_count >= threshold.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from .compose import (
    STATEMENT_DML,
    QueryShapeError,
    classify_statement,
    dialect_for,
    has_order_by,
    is_constant_query,
    parse_query,
)
from .types import NOSQL_TYPES, GradingTask

KIND_SELECT = 'select'
KIND_DML = 'dml'
KIND_NOSQL = 'nosql'
ALL_KINDS = (KIND_SELECT, KIND_DML, KIND_NOSQL)


@dataclass(frozen=True)
class CriterionSpec:
    id: str
    name: str
    description: str
    kinds: tuple[str, ...]


GENERAL: tuple[CriterionSpec, ...] = (
    CriterionSpec('execution', 'Запит виконується',
                  'Запит виконався без помилки.', ALL_KINDS),
    CriterionSpec('columns', 'Кількість стовпців',
                  'Стільки ж стовпців, скільки повертає еталон.', (KIND_SELECT, KIND_NOSQL)),
    CriterionSpec('column_names', 'Назви стовпців',
                  'Назви стовпців як в еталоні, без урахування регістру.', (KIND_SELECT,)),
    CriterionSpec('complete', 'Усі потрібні рядки є',
                  'Жоден рядок еталонного результату не пропущено.', (KIND_SELECT, KIND_NOSQL)),
    CriterionSpec('precise', 'Немає зайвих рядків',
                  'Результат не містить рядків, яких немає в еталоні.', (KIND_SELECT, KIND_NOSQL)),
    CriterionSpec('order', 'Порядок рядків',
                  'Рядки в тому ж порядку, що в еталоні. Еталон має містити ORDER BY.',
                  (KIND_SELECT, KIND_NOSQL)),
    CriterionSpec('reads_data', 'Відповідь отримана з таблиць',
                  'Запит читає дані з таблиць, а не містить готову відповідь.', (KIND_SELECT,)),
    CriterionSpec('state', 'Стан таблиць збігається',
                  'Після запиту вміст таблиць такий самий, як після еталонного.', (KIND_DML,)),
)
GENERAL_BY_ID = {spec.id: spec for spec in GENERAL}
ALWAYS_ON = frozenset({'execution'})
DEFAULT_OFF = frozenset({'column_names'})
RESULT_CRITERIA = frozenset({'columns', 'column_names', 'complete', 'precise', 'order'})


# ── task shape ──────────────────────────────────────────────────────────────

def task_kind(task: GradingTask) -> str:
    if task.db_type in NOSQL_TYPES:
        return KIND_NOSQL
    reference_kind = classify_statement(task.reference_query, dialect_for(task.db_type))
    if reference_kind == STATEMENT_DML:
        return KIND_DML
    if not task.is_select_task and task.reference_query and reference_kind != 'select':
        return KIND_DML
    return KIND_SELECT


def has_reference(task: GradingTask) -> bool:
    return bool(task.reference_query) or isinstance(task.expected_result, dict)


def reference_node(task: GradingTask):
    if not task.reference_query or task.db_type in NOSQL_TYPES:
        return None
    try:
        return parse_query(task.reference_query, dialect_for(task.db_type))
    except QueryShapeError:
        return None


def order_applicable(task: GradingTask, kind: str) -> bool:
    if kind == KIND_NOSQL:
        return True
    if kind != KIND_SELECT or not has_reference(task):
        return False
    if task.order_matters:
        return True
    node = reference_node(task)
    return node is not None and has_order_by(node)


def applicable_ids(task: GradingTask) -> list[str]:
    kind = task_kind(task)
    ids = []
    for spec in GENERAL:
        if kind not in spec.kinds:
            continue
        if spec.id in RESULT_CRITERIA and not has_reference(task):
            continue
        if spec.id == 'order' and not order_applicable(task, kind):
            continue
        if spec.id == 'reads_data':
            node = reference_node(task)
            if node is not None and is_constant_query(node):
                continue
        ids.append(spec.id)
    return ids


def default_enabled(task: GradingTask) -> list[str]:
    return [cid for cid in applicable_ids(task) if cid not in DEFAULT_OFF]


# ── configuration ───────────────────────────────────────────────────────────

def _threshold_of(config: Any) -> int:
    raw = config.get('threshold') if isinstance(config, dict) else None
    if isinstance(raw, bool) or not isinstance(raw, int) or raw < 0:
        return 0
    return raw


def resolve_config(task: GradingTask, config: Any) -> tuple[list[str], int]:
    """Enabled general criteria (catalog order) and the raw threshold; 0 means "all".

    Unknown or no-longer-applicable ids are dropped silently: the instructor may have
    edited the reference after saving the criteria, and grading must still work.
    """
    applicable = applicable_ids(task)
    if not isinstance(config, dict) or not config.get('enabled'):
        return default_enabled(task), _threshold_of(config)
    wanted = set(ALWAYS_ON)
    for cid in config.get('enabled') or []:
        if isinstance(cid, str):
            wanted.add(cid)
    return [cid for cid in applicable if cid in wanted], _threshold_of(config)


def derived_specs(task: GradingTask) -> list[tuple[str, str]]:
    specs: list[tuple[str, str]] = []
    if task.reference_query:
        for index, _ in enumerate(task.hidden, start=1):
            specs.append((f'dataset:{index}', f'Контрольний набір №{index}'))
    for keyword in task.required_keywords or []:
        if keyword and keyword.strip():
            specs.append((f'require:{keyword.strip()}', f'Використано {keyword.strip()}'))
    for keyword in task.forbidden_keywords or []:
        if keyword and keyword.strip():
            specs.append((f'forbid:{keyword.strip()}', f'Не використано {keyword.strip()}'))
    return specs


def effective_threshold(raw: int, total: int) -> int:
    return total if raw <= 0 or raw > total else raw


def describe(task: GradingTask, config: Any = None) -> dict:
    enabled, raw = resolve_config(task, config if config is not None else task.criteria)
    items = [{'id': cid, 'name': GENERAL_BY_ID[cid].name} for cid in enabled]
    items += [{'id': cid, 'name': name} for cid, name in derived_specs(task)]
    total = len(items)
    return {'criteria': items, 'total': total, 'threshold': effective_threshold(raw, total)}


def validate_config(task: GradingTask, config: Any) -> dict:
    """Normalize an instructor's criteria config or raise ValueError (Ukrainian text)."""
    if config in (None, '', {}):
        return {}
    if not isinstance(config, dict):
        raise ValueError('Критерії мають бути об\'єктом {"enabled": [...], "threshold": N}.')
    enabled = config.get('enabled', [])
    if enabled is None:
        enabled = []
    if not isinstance(enabled, list) or not all(isinstance(c, str) for c in enabled):
        raise ValueError('Поле enabled має бути списком ідентифікаторів критеріїв.')
    applicable = applicable_ids(task)
    for cid in enabled:
        if cid not in GENERAL_BY_ID:
            raise ValueError(f'Невідомий критерій: {cid}.')
        if cid not in applicable:
            if cid == 'order':
                raise ValueError('Критерій «Порядок рядків» потребує ORDER BY в еталонному запиті.')
            raise ValueError(f'Критерій «{GENERAL_BY_ID[cid].name}» не застосовний до цієї вправи.')
    threshold = config.get('threshold', 0)
    if threshold is None:
        threshold = 0
    if isinstance(threshold, bool) or not isinstance(threshold, int) or threshold < 0:
        raise ValueError('Поріг має бути цілим числом від 0.')
    wanted = set(enabled) | ALWAYS_ON
    return {'enabled': [cid for cid in applicable if cid in wanted], 'threshold': threshold}


def catalog_payload() -> list[dict]:
    return [{'id': s.id, 'name': s.name, 'description': s.description, 'kinds': list(s.kinds)}
            for s in GENERAL]
```

- [ ] **Step 5: Run the registry tests**

Run: `cd backend && .venv/Scripts/python manage.py test grading.test_criteria --settings=config.settings_test`
Expected: all 26 tests OK. Then `manage.py test grading` still OK (service untouched beyond the import move).

---

### Task 2: Evaluation context and SELECT criteria (`grading/criteria.py` part 2)

**Files:**
- Modify: `backend/grading/criteria.py` (append)
- Test: `backend/grading/test_criteria.py` (append)

**Interfaces:**
- Consumes `types.*`, `compare.compare`, `compose.*`, `normalize.*`, `sqlite_runner` / `sqlite_sequence_runner` from `grading/test_service.py` (tests import them).
- Produces `Verdict(passed: bool, detail: str = '')`, `CriteriaResult(items, passed_count, total, threshold, passed, context)`, `Context`, `evaluate(task, student_query, run, run_sequence=None) -> CriteriaResult`, `prepare_rows(db_type, rows)`, `strip_literals_and_comments(sql)`, `word_in(keyword, text)`, `MSG` dict of Ukrainian details.

- [ ] **Step 1: Write the failing evaluation tests (SELECT kind)**

Append to `backend/grading/test_criteria.py`:

```python
from grading.criteria import evaluate
from grading.test_service import PRIMARY as COMPANY, EMPTY_DEPT, COUNT_PER_DEPT, sqlite_runner

def company(reference=COUNT_PER_DEPT, **kw):
    return GradingTask(db_type='sqlite', reference_query=reference, primary=COMPANY, **kw)

def verdicts(result):
    return {item['id']: item['passed'] for item in result.items}

def detail(result, cid):
    return next(item['detail'] for item in result.items if item['id'] == cid)


class SelectEvaluationTests(unittest.TestCase):
    def test_correct_answer_passes_every_default_criterion(self):
        r = evaluate(company(), COUNT_PER_DEPT, sqlite_runner())
        self.assertEqual(verdicts(r), {'execution': True, 'columns': True, 'complete': True,
                                       'precise': True, 'reads_data': True})
        self.assertEqual((r.passed_count, r.total, r.threshold, r.passed), (5, 5, 5, True))

    def test_execution_error_fails_everything_with_one_reason(self):
        r = evaluate(company(), 'SELECT nope FROM nowhere', sqlite_runner())
        self.assertFalse(any(verdicts(r).values()))
        self.assertIn('no such table', detail(r, 'execution'))
        self.assertEqual(detail(r, 'complete'), 'Запит не виконався.')

    def test_two_statements_fail_execution_without_running(self):
        calls = []
        r = evaluate(company(), 'SELECT 1; SELECT 2', sqlite_runner(calls))
        self.assertFalse(r.passed)
        self.assertEqual(calls, [])
        self.assertIn('одна інструкція', detail(r, 'execution'))

    def test_dml_answer_to_select_task_fails_execution_without_running(self):
        calls = []
        r = evaluate(company(), 'DELETE FROM employees', sqlite_runner(calls))
        self.assertEqual(calls, [])
        self.assertIn('SELECT', detail(r, 'execution'))

    def test_column_count_mismatch_fails_result_criteria_only(self):
        r = evaluate(company(), 'SELECT name FROM departments', sqlite_runner())
        self.assertEqual(verdicts(r), {'execution': True, 'columns': False, 'complete': False,
                                       'precise': False, 'reads_data': True})
        self.assertEqual(detail(r, 'columns'), 'Очікується 2 стовпці, отримано 1.')
        self.assertEqual(detail(r, 'complete'), 'Кількість стовпців не збігається.')

    def test_missing_rows_fail_complete_but_not_precise(self):
        r = evaluate(company(),
                     "SELECT d.name, COUNT(e.id) FROM departments d LEFT JOIN employees e "
                     "ON e.dept_id = d.id WHERE d.id <> 3 GROUP BY d.name", sqlite_runner())
        self.assertEqual(verdicts(r)['complete'], False)
        self.assertEqual(verdicts(r)['precise'], True)
        self.assertIn('Підтримка', detail(r, 'complete'))

    def test_extra_rows_fail_precise_but_not_complete(self):
        r = evaluate(company('SELECT name FROM employees WHERE salary > 5000'),
                     'SELECT name FROM employees', sqlite_runner())
        self.assertEqual(verdicts(r)['complete'], True)
        self.assertEqual(verdicts(r)['precise'], False)
        self.assertIn('Зайві рядки', detail(r, 'precise'))

    def test_column_names_fail_alone(self):
        t = company('SELECT name AS employee FROM employees',
                    criteria={'enabled': ['columns', 'column_names', 'complete', 'precise']})
        r = evaluate(t, 'SELECT name FROM employees', sqlite_runner())
        self.assertEqual(verdicts(r), {'execution': True, 'columns': True, 'column_names': False,
                                       'complete': True, 'precise': True})
        self.assertEqual(detail(r, 'column_names'), 'Стовпець 1: очікується employee, отримано name.')

    def test_column_names_ignore_case(self):
        t = company('SELECT name AS Employee FROM employees', criteria={'enabled': ['column_names']})
        r = evaluate(t, 'SELECT name AS EMPLOYEE FROM employees', sqlite_runner())
        self.assertTrue(verdicts(r)['column_names'])

    def test_wrong_order_fails_only_order(self):
        r = evaluate(company('SELECT name FROM employees ORDER BY salary DESC'),
                     'SELECT name FROM employees ORDER BY salary', sqlite_runner())
        self.assertEqual(verdicts(r)['order'], False)
        self.assertEqual(verdicts(r)['complete'], True)
        self.assertEqual(detail(r, 'order'), 'Рядки правильні, але порядок інший.')

    def test_order_fails_with_reason_when_rows_are_wrong(self):
        r = evaluate(company('SELECT name FROM employees ORDER BY salary DESC'),
                     'SELECT name FROM employees WHERE salary > 5000 ORDER BY salary DESC',
                     sqlite_runner())
        self.assertEqual(detail(r, 'order'), 'Спершу виправте набір рядків.')

    def test_hardcoded_answer_fails_reads_data_only(self):
        r = evaluate(company('SELECT name FROM departments'),
                     "SELECT 'Розробка' UNION ALL SELECT 'Аналітика' UNION ALL SELECT 'Підтримка'",
                     sqlite_runner())
        self.assertEqual(verdicts(r)['reads_data'], False)
        self.assertEqual(verdicts(r)['complete'], True)

    def test_unparseable_query_is_graded_by_execution_only(self):
        # sqlglot cannot parse this SQLite-only syntax, the engine runs it fine.
        r = evaluate(company('SELECT name FROM employees', required_keywords=['WHERE']),
                     "SELECT name FROM employees WHERE name GLOB 'І*' OR 1 = 1", sqlite_runner())
        self.assertTrue(verdicts(r)['execution'])
        self.assertTrue(verdicts(r)['reads_data'])
        self.assertTrue(verdicts(r)['require:WHERE'])

    def test_reference_failure_blames_the_task(self):
        r = evaluate(company('SELECT nope FROM employees'), 'SELECT name FROM employees',
                     sqlite_runner())
        self.assertTrue(verdicts(r)['execution'])
        self.assertFalse(verdicts(r)['complete'])
        self.assertIn('Еталонний запит', detail(r, 'complete'))


class ThresholdTests(unittest.TestCase):
    def test_threshold_met_passes(self):
        t = company('SELECT name FROM employees ORDER BY salary DESC', criteria={'threshold': 5})
        r = evaluate(t, 'SELECT name FROM employees ORDER BY salary', sqlite_runner())
        self.assertEqual((r.passed_count, r.total, r.threshold), (5, 6, 5))
        self.assertTrue(r.passed)

    def test_threshold_not_met_fails(self):
        t = company('SELECT name FROM employees ORDER BY salary DESC', criteria={'threshold': 6})
        r = evaluate(t, 'SELECT name FROM employees ORDER BY salary', sqlite_runner())
        self.assertFalse(r.passed)

    def test_threshold_above_total_means_all(self):
        t = company(criteria={'threshold': 40})
        r = evaluate(t, COUNT_PER_DEPT, sqlite_runner())
        self.assertEqual(r.threshold, r.total)
        self.assertTrue(r.passed)

    def test_items_keep_catalog_order_then_derived(self):
        t = company(hidden=[EMPTY_DEPT], required_keywords=['LEFT JOIN'],
                    criteria={'enabled': ['precise', 'columns']})
        r = evaluate(t, COUNT_PER_DEPT, sqlite_runner())
        self.assertEqual([i['id'] for i in r.items],
                         ['execution', 'columns', 'precise', 'dataset:1', 'require:LEFT JOIN'])
```

- [ ] **Step 2: Run to see them fail**

Run: `cd backend && .venv/Scripts/python manage.py test grading.test_criteria --settings=config.settings_test`
Expected: ImportError on `evaluate`.

- [ ] **Step 3: Append the evaluation code to `grading/criteria.py`**

Add these imports at the top of the file (merge with the existing ones):

```python
import re
import time
from functools import cached_property
from typing import Callable, Sequence

from . import compare as cmp
from .compose import (
    STATEMENT_MULTIPLE,
    build_symmetric_difference,
    constructs,
    created_table,
    parse_statement,
    reads_data,
    select_all_sql,
    supports_except_all,
    tables_in_schema,
)
from .normalize import canonical_json, describe_row
from .types import (
    PURPOSE_DIFF, PURPOSE_REFERENCE, PURPOSE_STUDENT, CheckDataset, Execution, RunFn, SequenceRunFn,
)
```

Then append:

```python
# ── evaluation ──────────────────────────────────────────────────────────────

HIDDEN_BUDGET_SECONDS = 45.0

MSG = {
    'multiple': 'Очікується рівно одна інструкція.',
    'dml_for_select': 'Очікується SELECT, а надіслано інструкцію зміни даних.',
    'blocked': 'Запит не виконався.',
    'reference': 'Еталонний запит не виконується. Повідомте викладача.',
    'columns_block': 'Кількість стовпців не збігається.',
    'rows_first': 'Спершу виправте набір рядків.',
    'truncated': 'Результат завеликий, щоб порівняти його надійно.',
    'truncated_order': 'Результат завеликий для перевірки порядку.',
    'order': 'Рядки правильні, але порядок інший.',
    'hardcode': 'Запит не звертається до жодної таблиці.',
    'budget': 'Перевірку не встигли виконати. Спростіть запит або спробуйте ще раз.',
    'dataset': 'Не збіглося на контрольних даних.',
    'mismatch': 'Результат не збігається з еталоном.',
    'no_result': 'Запит не повернув результату.',
}


@dataclass
class Verdict:
    passed: bool
    detail: str = ''


@dataclass
class CriteriaResult:
    items: list[dict]
    passed_count: int
    total: int
    threshold: int
    passed: bool
    context: 'Context'


_LITERAL_OR_COMMENT = re.compile(
    r"""'(?:[^']|'')*'|"(?:[^"]|"")*"|--[^\n]*|/\*.*?\*/""",
    re.DOTALL,
)


def strip_literals_and_comments(sql: str) -> str:
    return _LITERAL_OR_COMMENT.sub(' ', sql or '')


def word_in(keyword: str, text: str) -> bool:
    pattern = r'\b' + r'\s+'.join(re.escape(p) for p in keyword.split()) + r'\b'
    return re.search(pattern, text, re.IGNORECASE) is not None


def prepare_rows(db_type: str, rows: Sequence[Sequence[Any]]) -> list[list[Any]]:
    if db_type != 'mongodb':
        return [list(r) for r in rows]
    return [[_canonical_document(cell) for cell in row] for row in rows]


def _canonical_document(cell: Any) -> Any:
    """Stable text for a MongoDB document, ignoring the engine-generated top-level _id."""
    import json
    if isinstance(cell, str):
        try:
            parsed = json.loads(cell)
        except (ValueError, TypeError):
            return cell
    else:
        parsed = cell
    if isinstance(parsed, dict):
        return canonical_json({k: v for k, v in parsed.items() if k != '_id'})
    if isinstance(parsed, list):
        return canonical_json(parsed)
    return cell


def _try_parse(sql: str, db_type: str):
    if not sql or db_type in NOSQL_TYPES:
        return None
    try:
        return parse_query(sql, dialect_for(db_type))
    except QueryShapeError:
        return None


class Context:
    """Everything the criteria may ask about one submission, computed on first use."""

    def __init__(self, task: GradingTask, student_query: str, run: RunFn,
                 run_sequence: Optional[SequenceRunFn]):
        self.task = task
        self.student_query = student_query
        self.run = run
        self.run_sequence = run_sequence
        self.kind = task_kind(task)
        self.dialect = dialect_for(task.db_type)
        self.shape_error = ''
        if self.kind != KIND_NOSQL:
            student_kind = classify_statement(student_query, self.dialect)
            if student_kind == STATEMENT_MULTIPLE:
                self.shape_error = MSG['multiple']
            elif self.kind == KIND_SELECT and student_kind == STATEMENT_DML:
                self.shape_error = MSG['dml_for_select']
        self._hidden_started: Optional[float] = None
        self._dataset_cache: dict[int, Verdict] = {}

    # ── parsing ──
    @cached_property
    def student_node(self):
        return _try_parse(self.student_query, self.task.db_type)

    @cached_property
    def reference_node(self):
        return reference_node(self.task)

    @cached_property
    def constructs(self) -> set[str]:
        return constructs(self.student_node) if self.student_node is not None else set()

    @cached_property
    def stripped_text(self) -> str:
        return strip_literals_and_comments(self.student_query)

    # ── execution ──
    @cached_property
    def dml_tables(self) -> list[str]:
        if self.kind != KIND_DML or not self.task.reference_query:
            return []
        tables = tables_in_schema(self.task.primary.schema_sql, self.dialect)
        created = created_table(parse_statement(self.task.reference_query, self.dialect))
        if created and created.lower() not in {t.lower() for t in tables}:
            tables.append(created)
        return tables

    @cached_property
    def uses_table_state(self) -> bool:
        return bool(self.run_sequence is not None and self.dml_tables and self.task.reference_query)

    @cached_property
    def dml_runs(self) -> tuple[list[Execution], list[Execution]]:
        selects = [select_all_sql(t, self.dialect) for t in self.dml_tables]
        student = self.run_sequence([self.student_query, *selects], self.task.primary, PURPOSE_STUDENT)
        reference = self.run_sequence([self.task.reference_query, *selects], self.task.primary,
                                      PURPOSE_REFERENCE)
        return list(student), list(reference)

    @cached_property
    def student_exec(self) -> Execution:
        if self.shape_error:
            return Execution(success=False, error=self.shape_error)
        if self.uses_table_state:
            runs = self.dml_runs[0]
            return runs[0] if runs else Execution(False, error='немає результату')
        return self.run(self.student_query, self.task.primary, PURPOSE_STUDENT)

    @cached_property
    def reference(self) -> tuple[Optional[Execution], bool]:
        """(reference execution, came from a stored snapshot)."""
        task = self.task
        if self.kind == KIND_DML:
            if self.uses_table_state:
                runs = self.dml_runs[1]
                return (runs[0] if runs else Execution(False, error='немає результату')), False
            if task.reference_query:
                return self.run(task.reference_query, task.primary, PURPOSE_REFERENCE), False
            return None, False
        if task.reference_query:
            return self.run(task.reference_query, task.primary, PURPOSE_REFERENCE), False
        snapshot = task.expected_result
        if isinstance(snapshot, dict):
            return Execution(
                success=True,
                columns=list(snapshot.get('columns') or []),
                rows=[list(r) for r in (snapshot.get('rows') or [])],
                truncated=bool(snapshot.get('truncated', False)),
            ), True
        return None, False

    @property
    def reference_exec(self) -> Optional[Execution]:
        return self.reference[0]

    @property
    def from_snapshot(self) -> bool:
        return self.reference[1]

    @property
    def reference_failed(self) -> bool:
        return self.reference_exec is not None and not self.reference_exec.success

    # ── comparison on the primary dataset ──
    @cached_property
    def student_rows(self) -> list[list[Any]]:
        return prepare_rows(self.task.db_type, self.student_exec.rows)

    @cached_property
    def expected_rows(self) -> list[list[Any]]:
        return prepare_rows(self.task.db_type, self.reference_exec.rows) if self.reference_exec else []

    @cached_property
    def diff(self) -> Optional[cmp.Diff]:
        """Unordered diff; None when there is nothing to compare against."""
        if not self.student_exec.success or self.reference_exec is None or self.reference_failed:
            return None
        student, expected = self.student_exec, self.reference_exec
        d = cmp.compare(student.columns, self.student_rows, expected.columns, self.expected_rows,
                        ordered=False, student_truncated=student.truncated,
                        expected_truncated=expected.truncated, lenient_numbers=self.from_snapshot)
        if d.kind == cmp.KIND_TRUNCATED:
            verdict = self.diff_in_database(self.task.primary)
            if verdict is not None:
                self.truncated_but_decided = True
                return cmp.Diff(equal=verdict, kind=cmp.KIND_OK if verdict else cmp.KIND_ROWS,
                                overlap=1.0 if verdict else 0.0)
        return d

    truncated_but_decided = False

    @property
    def truncated_undecided(self) -> bool:
        return self.diff is not None and self.diff.kind == cmp.KIND_TRUNCATED

    @cached_property
    def ordered_diff(self) -> Optional[cmp.Diff]:
        if self.diff is None or self.diff.kind in (cmp.KIND_TRUNCATED, cmp.KIND_COLUMN_COUNT):
            return None
        return cmp.compare(self.student_exec.columns, self.student_rows,
                           self.reference_exec.columns, self.expected_rows,
                           ordered=True, lenient_numbers=self.from_snapshot)

    # ── in-database difference and hidden datasets ──
    def diff_in_database(self, dataset: CheckDataset) -> Optional[bool]:
        """Symmetric difference inside the engine; None when the engine cannot do it."""
        task = self.task
        if self.student_node is None or not task.reference_query or not supports_except_all(task.db_type):
            return None
        try:
            sql = build_symmetric_difference(self.student_query, task.reference_query, task.db_type)
        except Exception:  # noqa: BLE001 - any composition failure means "compare in Python"
            return None
        result = self.run(sql, dataset, PURPOSE_DIFF)
        if result.success:
            return len(result.rows) == 0
        if result.timed_out:
            return False
        return None

    def matches_on_dataset(self, dataset: CheckDataset) -> bool:
        verdict = self.diff_in_database(dataset)
        if verdict is not None:
            return verdict
        student = self.run(self.student_query, dataset, PURPOSE_STUDENT)
        if not student.success:
            return False
        reference = self.run(self.task.reference_query, dataset, PURPOSE_REFERENCE)
        if not reference.success:
            return False
        d = cmp.compare(student.columns, prepare_rows(self.task.db_type, student.rows),
                        reference.columns, prepare_rows(self.task.db_type, reference.rows),
                        student_truncated=student.truncated, expected_truncated=reference.truncated)
        return d.equal

    def dataset_verdict(self, index: int) -> Verdict:
        """Verdict for hidden dataset number `index` (1-based), within the shared time budget."""
        if index in self._dataset_cache:
            return self._dataset_cache[index]
        dataset = self.task.hidden[index - 1]
        if self.diff is not None and self.diff.kind == cmp.KIND_COLUMN_COUNT:
            verdict = Verdict(False, MSG['columns_block'])
        else:
            if self._hidden_started is None:
                self._hidden_started = time.monotonic()
            if time.monotonic() - self._hidden_started > HIDDEN_BUDGET_SECONDS:
                verdict = Verdict(False, MSG['budget'])
            elif self.matches_on_dataset(dataset):
                verdict = Verdict(True)
            else:
                verdict = Verdict(False, dataset.targets or MSG['dataset'])
        self._dataset_cache[index] = verdict
        return verdict

    # ── keywords ──
    def uses(self, keyword: str) -> bool:
        return keyword.upper() in self.constructs or word_in(keyword, self.stripped_text)


# ── criterion evaluators (SELECT / NoSQL) ──────────────────────────────────

def _execution(ctx: Context) -> Verdict:
    ex = ctx.student_exec
    if ex.success:
        return Verdict(True)
    return Verdict(False, ex.error or MSG['blocked'])


def _columns(ctx: Context) -> Verdict:
    d = ctx.diff
    if d is None:
        return Verdict(False, MSG['reference'])
    if d.kind == cmp.KIND_COLUMN_COUNT:
        return Verdict(False, f'Очікується {d.expected_columns} стовпці, отримано {d.student_columns}.')
    if not ctx.reference_exec.columns and not ctx.student_exec.columns:
        return Verdict(False, MSG['no_result'])
    return Verdict(True)


def _column_names(ctx: Context) -> Verdict:
    d = ctx.diff
    if d is None or d.kind == cmp.KIND_COLUMN_COUNT:
        return Verdict(False, MSG['columns_block'])
    expected = [c.strip().lower() for c in ctx.reference_exec.columns]
    actual = [c.strip().lower() for c in ctx.student_exec.columns]
    for position, (e, a) in enumerate(zip(expected, actual), start=1):
        if e != a:
            return Verdict(False, f'Стовпець {position}: очікується '
                                  f'{ctx.reference_exec.columns[position - 1]}, '
                                  f'отримано {ctx.student_exec.columns[position - 1]}.')
    return Verdict(True)


def _rows_guard(ctx: Context) -> Optional[Verdict]:
    d = ctx.diff
    if d is None:
        return Verdict(False, MSG['reference'])
    if d.kind == cmp.KIND_COLUMN_COUNT:
        return Verdict(False, MSG['columns_block'])
    if d.kind == cmp.KIND_TRUNCATED:
        return Verdict(False, MSG['truncated'])
    return None


def _complete(ctx: Context) -> Verdict:
    guard = _rows_guard(ctx)
    if guard:
        return guard
    d = ctx.diff
    if d.missing:
        return Verdict(False, 'Не вистачає рядків: ' + d.describe_missing() + '.')
    if not d.equal and not d.extra:
        return Verdict(False, MSG['mismatch'])   # decided inside the database, no row detail
    return Verdict(True)


def _precise(ctx: Context) -> Verdict:
    guard = _rows_guard(ctx)
    if guard:
        return guard
    d = ctx.diff
    if d.extra:
        return Verdict(False, 'Зайві рядки: ' + d.describe_extra() + '.')
    if not d.equal and not d.missing:
        return Verdict(False, MSG['mismatch'])
    return Verdict(True)


def _order(ctx: Context) -> Verdict:
    guard = _rows_guard(ctx)
    if guard:
        return guard
    if not ctx.diff.equal:
        return Verdict(False, MSG['rows_first'])
    if ctx.truncated_but_decided or ctx.ordered_diff is None:
        return Verdict(False, MSG['truncated_order'])
    return Verdict(True) if ctx.ordered_diff.equal else Verdict(False, MSG['order'])


def _reads_data(ctx: Context) -> Verdict:
    node = ctx.student_node
    if node is None:
        return Verdict(True)   # cannot tell; the engine ran it, give the benefit of the doubt
    return Verdict(True) if reads_data(node) else Verdict(False, MSG['hardcode'])


def _state(ctx: Context) -> Verdict:
    task = ctx.task
    if not ctx.uses_table_state:
        # Legacy fallback: no sequence runner or no readable schema.
        reference = ctx.reference_exec
        if reference is None:
            return Verdict(True)
        same = reference.affected_rows == ctx.student_exec.affected_rows
        return Verdict(same, '' if same else f'Змінених рядків: очікується {reference.affected_rows}, '
                                              f'отримано {ctx.student_exec.affected_rows}.')
    student_results, reference_results = ctx.dml_runs
    differing: list[str] = []
    details: list[str] = []
    for index, table in enumerate(ctx.dml_tables, start=1):
        student_state = student_results[index] if index < len(student_results) else None
        reference_state = reference_results[index] if index < len(reference_results) else None
        if reference_state is None or not reference_state.success:
            continue   # the reference cannot see this table either (e.g. it drops it)
        if student_state is None or not student_state.success:
            differing.append(table)
            details.append(f'таблиця {table} недоступна або відсутня')
            continue
        d = cmp.compare(student_state.columns, student_state.rows,
                        reference_state.columns, reference_state.rows)
        if d.equal:
            continue
        differing.append(table)
        if d.kind == cmp.KIND_COLUMN_COUNT:
            details.append(f'таблиця {table}: очікується {d.expected_columns} стовпців, '
                           f'отримано {d.student_columns}')
        else:
            if d.missing:
                details.append(f'таблиця {table}, бракує рядків: {d.describe_missing()}')
            if d.extra:
                details.append(f'таблиця {table}, зайві рядки: {d.describe_extra()}')
    if differing:
        return Verdict(False, '; '.join(details) + '.')
    return Verdict(True)


EVALUATORS: dict[str, Callable[[Context], Verdict]] = {
    'execution': _execution,
    'columns': _columns,
    'column_names': _column_names,
    'complete': _complete,
    'precise': _precise,
    'order': _order,
    'reads_data': _reads_data,
    'state': _state,
}


def _derived(ctx: Context, cid: str) -> Verdict:
    kind, _, value = cid.partition(':')
    if kind == 'dataset':
        return ctx.dataset_verdict(int(value))
    if kind == 'require':
        return Verdict(True) if ctx.uses(value) else Verdict(False, f'Не використано {value}.')
    if kind == 'forbid':
        return Verdict(False, f'Використано заборонене {value}.') if ctx.uses(value) else Verdict(True)
    return Verdict(False, f'Невідомий критерій {cid}.')


def evaluate(task: GradingTask, student_query: str, run: RunFn,
             run_sequence: Optional[SequenceRunFn] = None) -> CriteriaResult:
    enabled, raw_threshold = resolve_config(task, task.criteria)
    derived = derived_specs(task)
    ctx = Context(task, student_query, run, run_sequence)

    items: list[dict] = []

    def add(cid: str, name: str, verdict: Verdict) -> None:
        items.append({'id': cid, 'name': name, 'passed': bool(verdict.passed),
                      'detail': verdict.detail or ''})

    execution = _execution(ctx)
    add('execution', GENERAL_BY_ID['execution'].name, execution)

    blocked = ''
    if not execution.passed:
        blocked = MSG['blocked']
    elif ctx.reference_failed:
        blocked = MSG['reference']

    for cid in enabled:
        if cid == 'execution':
            continue
        add(cid, GENERAL_BY_ID[cid].name,
            Verdict(False, blocked) if blocked else EVALUATORS[cid](ctx))
    for cid, name in derived:
        add(cid, name, Verdict(False, blocked) if blocked else _derived(ctx, cid))

    total = len(items)
    passed_count = sum(1 for item in items if item['passed'])
    threshold = effective_threshold(raw_threshold, total)
    return CriteriaResult(items, passed_count, total, threshold, passed_count >= threshold, ctx)
```

Note on `_columns`: the detail uses the word "стовпці" for every count; keep it simple, tests assert this exact text.

- [ ] **Step 4: Run the tests**

Run: `cd backend && .venv/Scripts/python manage.py test grading.test_criteria --settings=config.settings_test`
Expected: all OK (26 + 19). If `test_unparseable_query_is_graded_by_execution_only` fails because sqlglot does parse GLOB, change the query to `"SELECT name FROM employees WHERE name REGEXP 'x' OR 1 = 1"`; if that is parsed as well, use `"SELECT name FROM employees WHERE 1 = 1 COLLATE NOCASE"` and keep whichever `classify_statement` reports as `invalid` (check with a one-off `python -c`).

---

### Task 3: Hidden datasets, budget, truncation, keywords

**Files:**
- Test: `backend/grading/test_criteria.py` (append)
- Modify: `backend/grading/criteria.py` only if a test exposes a gap

**Interfaces:**
- Consumes `Context.dataset_verdict`, `_derived`, `MSG`.

- [ ] **Step 1: Write the failing tests**

```python
from grading.test_service import BOUNDARY, DUPLICATES, NOBODY, PURPOSE_DIFF


class HiddenDatasetTests(unittest.TestCase):
    def test_inner_join_fails_only_the_dataset_criterion(self):
        t = company(hidden=[EMPTY_DEPT])
        r = evaluate(t, "SELECT d.name, COUNT(e.id) FROM departments d JOIN employees e "
                        "ON e.dept_id = d.id GROUP BY d.name", sqlite_runner())
        self.assertEqual(verdicts(r)['complete'], True)
        self.assertEqual(verdicts(r)['dataset:1'], False)
        self.assertEqual(detail(r, 'dataset:1'), 'відділ без працівників')

    def test_each_dataset_is_its_own_criterion(self):
        t = company('SELECT name FROM employees WHERE salary >= 5000', hidden=[BOUNDARY, NOBODY])
        r = evaluate(t, 'SELECT name FROM employees WHERE salary > 5000', sqlite_runner())
        self.assertEqual(verdicts(r)['dataset:1'], False)
        self.assertEqual(verdicts(r)['dataset:2'], True)

    def test_datasets_still_run_when_primary_rows_differ(self):
        calls = []
        t = company('SELECT name FROM employees WHERE salary >= 5000', hidden=[NOBODY])
        r = evaluate(t, 'SELECT name FROM employees WHERE salary > 100000', sqlite_runner(calls))
        # primary student + primary reference, then the hidden dataset (student + reference)
        self.assertEqual(len(calls), 4)
        self.assertFalse(verdicts(r)['complete'])
        self.assertTrue(verdicts(r)['dataset:1'])   # both queries are empty on "порожня вибірка"

    def test_datasets_do_not_run_when_column_count_differs(self):
        calls = []
        t = company(hidden=[EMPTY_DEPT])
        r = evaluate(t, 'SELECT name FROM departments', sqlite_runner(calls))
        self.assertEqual(len(calls), 2)   # student + reference on the primary dataset only
        self.assertEqual(detail(r, 'dataset:1'), 'Кількість стовпців не збігається.')

    def test_budget_exhaustion_fails_remaining_datasets(self):
        from grading import criteria as mod
        original = mod.HIDDEN_BUDGET_SECONDS
        mod.HIDDEN_BUDGET_SECONDS = -1.0
        try:
            t = company(hidden=[EMPTY_DEPT, BOUNDARY])
            r = evaluate(t, COUNT_PER_DEPT, sqlite_runner())
        finally:
            mod.HIDDEN_BUDGET_SECONDS = original
        self.assertFalse(verdicts(r)['dataset:1'])
        self.assertEqual(detail(r, 'dataset:2'), mod.MSG['budget'])
        self.assertFalse(r.passed)


class KeywordTests(unittest.TestCase):
    def test_required_construct_from_ast(self):
        t = company(required_keywords=['LEFT JOIN', 'GROUP BY'])
        r = evaluate(t, COUNT_PER_DEPT, sqlite_runner())
        self.assertTrue(verdicts(r)['require:LEFT JOIN'])
        self.assertTrue(verdicts(r)['require:GROUP BY'])

    def test_keyword_inside_literal_does_not_count(self):
        t = company('SELECT name FROM employees', required_keywords=['WHERE'])
        r = evaluate(t, "SELECT name FROM employees", sqlite_runner())
        self.assertFalse(verdicts(r)['require:WHERE'])
        r2 = evaluate(t, "SELECT name FROM employees -- WHERE", sqlite_runner())
        self.assertFalse(verdicts(r2)['require:WHERE'])

    def test_forbidden_subquery(self):
        t = company('SELECT name FROM employees WHERE dept_id = 1', forbidden_keywords=['SUBQUERY'])
        r = evaluate(t, "SELECT name FROM employees WHERE dept_id IN (SELECT id FROM departments "
                        "WHERE name = 'Розробка')", sqlite_runner())
        self.assertFalse(verdicts(r)['forbid:SUBQUERY'])
        self.assertEqual(detail(r, 'forbid:SUBQUERY'), 'Використано заборонене SUBQUERY.')


class TruncationTests(unittest.TestCase):
    def fake_runner(self, diff_rows, student_truncated=True):
        def run(sql, dataset, purpose):
            if purpose == PURPOSE_DIFF:
                return Execution(True, ['a'], diff_rows)
            return Execution(True, ['a'], [[1]], truncated=student_truncated)
        return run

    def test_sqlite_cannot_decide_a_truncated_result(self):
        r = evaluate(company('SELECT a FROM t'), 'SELECT a FROM t', self.fake_runner([]))
        self.assertFalse(verdicts(r)['complete'])
        self.assertEqual(detail(r, 'complete'), MSG['truncated'])

    def test_postgres_decides_in_database(self):
        t = GradingTask(db_type='postgresql', reference_query='SELECT a FROM t ORDER BY a',
                        primary=PRIMARY)
        r = evaluate(t, 'SELECT a FROM t', self.fake_runner([]))
        self.assertTrue(verdicts(r)['complete'] and verdicts(r)['precise'])
        self.assertEqual(detail(r, 'order'), MSG['truncated_order'])
        r2 = evaluate(t, 'SELECT a FROM t', self.fake_runner([[5]]))
        self.assertFalse(verdicts(r2)['complete'])
```

(`Execution` and `MSG` imports: add `from grading.criteria import MSG` and `from grading.service import Execution` at the top of the test file.)

- [ ] **Step 2: Run, fix, re-run**

Run: `cd backend && .venv/Scripts/python manage.py test grading.test_criteria --settings=config.settings_test`
Expected: all OK. Likely gaps to fix in `criteria.py` if they fail: `_complete`/`_precise` when `diff.equal` is False via the in-database path (both `missing` and `extra` empty) — handled by the `MSG['dataset']` branch; keep it.

---

### Task 4: DML state, NoSQL and reference-less exercises

**Files:**
- Test: `backend/grading/test_criteria.py` (append)
- Modify: `backend/grading/criteria.py` only on failures

- [ ] **Step 1: Write the failing tests**

```python
from grading.test_service import sqlite_sequence_runner


class DmlTests(unittest.TestCase):
    def test_equivalent_update_passes_state(self):
        t = company('UPDATE employees SET salary = salary * 2 WHERE dept_id = 1')
        r = evaluate(t, 'UPDATE employees SET salary = salary + salary WHERE dept_id = 1',
                     sqlite_runner(), sqlite_sequence_runner())
        self.assertEqual(verdicts(r), {'execution': True, 'state': True})
        self.assertTrue(r.passed)

    def test_delete_does_not_pass_an_update_exercise(self):
        t = company('UPDATE employees SET salary = 0 WHERE dept_id = 1')
        r = evaluate(t, 'DELETE FROM employees WHERE dept_id = 1',
                     sqlite_runner(), sqlite_sequence_runner())
        self.assertFalse(verdicts(r)['state'])
        self.assertIn('employees', detail(r, 'state'))

    def test_dml_syntax_error_fails_both(self):
        t = company('DELETE FROM employees WHERE dept_id = 1')
        r = evaluate(t, 'DELETE FROM', sqlite_runner(), sqlite_sequence_runner())
        self.assertEqual(verdicts(r), {'execution': False, 'state': False})

    def test_without_sequence_runner_affected_rows_decide(self):
        t = company('DELETE FROM employees WHERE dept_id = 1')
        r = evaluate(t, 'DELETE FROM employees WHERE dept_id = 2', sqlite_runner())
        self.assertTrue(verdicts(r)['state'])   # both delete two rows; legacy fallback only
        r2 = evaluate(t, 'DELETE FROM employees WHERE dept_id = 3', sqlite_runner())
        self.assertFalse(verdicts(r2)['state'])

    def test_create_table_compares_the_new_table(self):
        t = company("CREATE TABLE archive AS SELECT * FROM employees WHERE dept_id = 1")
        r = evaluate(t, "CREATE TABLE archive AS SELECT * FROM employees WHERE dept_id = 2",
                     sqlite_runner(), sqlite_sequence_runner())
        self.assertFalse(verdicts(r)['state'])
        self.assertIn('archive', detail(r, 'state'))

    def test_keywords_apply_to_dml(self):
        t = company('DELETE FROM employees WHERE dept_id = 1', required_keywords=['WHERE'])
        r = evaluate(t, 'DELETE FROM employees', sqlite_runner(), sqlite_sequence_runner())
        self.assertFalse(verdicts(r)['require:WHERE'])


class NoSqlTests(unittest.TestCase):
    def mongo_runner(self, rows_by_purpose):
        def run(query, dataset, purpose):
            return Execution(True, ['document'], rows_by_purpose[purpose])
        return run

    def test_documents_match_regardless_of_key_order_and_id(self):
        t = GradingTask(db_type='mongodb', reference_query='db.t.find({})', primary=PRIMARY,
                        required_keywords=['find'])
        run = self.mongo_runner({
            PURPOSE_STUDENT: [['{"_id": "a1", "x": 1, "y": 2}']],
            PURPOSE_REFERENCE: [['{"y": 2, "x": 1, "_id": "b2"}']],
        })
        r = evaluate(t, 'db.t.find({})', run)
        self.assertEqual(verdicts(r), {'execution': True, 'columns': True, 'complete': True,
                                       'precise': True, 'order': True, 'require:find': True})

    def test_different_documents_fail(self):
        t = GradingTask(db_type='mongodb', reference_query='db.t.find({})', primary=PRIMARY)
        run = self.mongo_runner({PURPOSE_STUDENT: [['{"x": 1}']], PURPOSE_REFERENCE: [['{"x": 2}']]})
        r = evaluate(t, 'db.t.find({x: 1})', run)
        self.assertFalse(verdicts(r)['complete'])
        self.assertFalse(verdicts(r)['precise'])


class ReferenceModesTests(unittest.TestCase):
    def test_snapshot_is_used_when_no_reference_query(self):
        t = company('', expected_result={'columns': ['name'], 'rows': [['Іваненко'], ['Петренко']]})
        r = evaluate(t, "SELECT name FROM employees WHERE dept_id = 1", sqlite_runner())
        self.assertTrue(r.passed)
        self.assertNotIn('order', verdicts(r))

    def test_free_exercise_passes_on_execution(self):
        r = evaluate(company(''), 'SELECT 1', sqlite_runner())
        self.assertEqual(verdicts(r), {'execution': True, 'reads_data': False})
        self.assertFalse(r.passed)   # constant answers never pass, even without a reference
        r2 = evaluate(company(''), 'SELECT name FROM employees', sqlite_runner())
        self.assertTrue(r2.passed)
```

- [ ] **Step 2: Run, fix, re-run**

Run: `cd backend && .venv/Scripts/python manage.py test grading.test_criteria --settings=config.settings_test`
Expected: all OK. Known fix likely needed: in `Context.__init__` DML kind, a student SELECT answer to a DML task must not be shape-rejected (only `MULTIPLE` is); verify `test_delete_does_not_pass_an_update_exercise` runs through `dml_runs`.

---

### Task 5: Rewire `service.grade()` and the existing service tests

**Files:**
- Modify: `backend/grading/service.py` (rewrite; keeps re-exports)
- Modify: `backend/grading/runner.py:91-130` (`build_task(..., criteria=None)`)
- Modify: `backend/grading/mutants.py:19` (import `prepare_rows` from `.criteria`)
- Modify: `backend/grading/test_service.py`, `backend/grading/test_service_review.py`

**Interfaces:**
- Produces `service.grade(task, student_query, run, run_sequence=None) -> GradeResult` where `GradeResult(score: Decimal, max_score: int, passed: bool, feedback: dict, execution: Execution)`; `feedback` keys: `mode, criteria, checks, passed_count, total, threshold, message, hints, result_match, keywords_missing, forbidden_used, failed_datasets, datasets_checked, missing_rows, extra_rows`.
- `runner.build_task(db_type, *, reference_query, dataset, check_datasets, required_keywords=None, forbidden_keywords=None, order_matters=False, max_score=100, query_type='select', expected_result=None, criteria=None)`.

- [ ] **Step 1: Rewrite `service.py`**

Replace the whole file with:

```python
"""Grading orchestration: evaluate the criteria, apply the threshold, build the feedback.

Execution is injected as a callback, so this module knows nothing about Docker,
sessions or Django models and can be tested with a fake runner.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

from . import compare as cmp
from .criteria import KIND_DML, CriteriaResult, evaluate, prepare_rows
from .normalize import describe_row
from .types import (  # noqa: F401 - re-exported for callers and tests
    NOSQL_TYPES,
    PURPOSE_DIFF,
    PURPOSE_REFERENCE,
    PURPOSE_STUDENT,
    SELECT_TASK_TYPES,
    CheckDataset,
    Execution,
    GradingTask,
    RunFn,
    SequenceRunFn,
)

MODE_RESULT = 'result'
MODE_EXECUTION = 'execution'

_prepare_rows = prepare_rows   # legacy name used by mutants.py


@dataclass
class GradeResult:
    score: Decimal
    max_score: int
    passed: bool
    feedback: dict
    execution: Execution

    @property
    def percent(self) -> float:
        return 0.0 if not self.max_score else float(self.score) / self.max_score * 100


def grade(task: GradingTask, student_query: str, run: RunFn,
          run_sequence: Optional[SequenceRunFn] = None) -> GradeResult:
    result = evaluate(task, student_query, run, run_sequence)
    score = (Decimal(task.max_score) if result.passed else Decimal(0)).quantize(
        Decimal('0.01'), rounding=ROUND_HALF_UP)
    return GradeResult(score, task.max_score, result.passed, _feedback(task, result),
                       result.context.student_exec)


def _feedback(task: GradingTask, result: CriteriaResult) -> dict:
    ctx = result.context
    items = result.items
    by_id = {item['id']: item for item in items}
    failed = [item for item in items if not item['passed']]

    hints: list[str] = []
    for item in failed:
        text = item['detail']
        if text and text not in hints:
            hints.append(text)

    missing_rows: list[str] = []
    extra_rows: list[str] = []
    diff = ctx.diff if ctx.kind != KIND_DML else None
    if diff is not None and diff.kind == cmp.KIND_ROWS:
        missing_rows = [describe_row(r) for r in diff.missing[:5]]
        extra_rows = [describe_row(r) for r in diff.extra[:5]]

    failed_datasets = []
    datasets_checked = 0
    for item in items:
        if item['id'].startswith('dataset:'):
            datasets_checked += 1
            if not item['passed']:
                dataset = task.hidden[int(item['id'].split(':')[1]) - 1]
                failed_datasets.append({'name': dataset.name, 'targets': dataset.targets})

    if ctx.kind == KIND_DML:
        result_match = bool(by_id.get('state', {}).get('passed'))
    else:
        result_match = bool(by_id.get('complete', {}).get('passed')) and \
            bool(by_id.get('precise', {}).get('passed'))

    if result.passed:
        message = f'Зараховано: {result.passed_count} із {result.total}'
    else:
        message = (f'Не зараховано: {result.passed_count} із {result.total}, '
                   f'потрібно {result.threshold}')

    return {
        'mode': MODE_EXECUTION if ctx.kind == KIND_DML else MODE_RESULT,
        'criteria': items,
        'checks': [{'code': i['id'], 'name': i['name'], 'passed': i['passed'],
                    **({'detail': i['detail']} if i['detail'] else {})} for i in items],
        'passed_count': result.passed_count,
        'total': result.total,
        'threshold': result.threshold,
        'message': message,
        'hints': hints,
        'result_match': result_match,
        'keywords_missing': [i['id'][len('require:'):] for i in failed if i['id'].startswith('require:')],
        'forbidden_used': [i['id'][len('forbid:'):] for i in failed if i['id'].startswith('forbid:')],
        'failed_datasets': failed_datasets,
        'datasets_checked': 1 + datasets_checked,
        'missing_rows': missing_rows,
        'extra_rows': extra_rows,
    }
```

In `runner.py`: add `criteria: Optional[dict] = None` to `build_task`'s keyword arguments and pass `criteria=criteria if isinstance(criteria, dict) else None` into `GradingTask(...)`.

In `mutants.py` line 19 change to:
`from .criteria import prepare_rows as _prepare_rows` and
`from .types import CheckDataset, Execution, PURPOSE_REFERENCE, RunFn`.

- [ ] **Step 2: Run the whole grading suite and triage**

Run: `cd backend && .venv/Scripts/python manage.py test grading --settings=config.settings_test 2>&1 | grep -E "^(FAIL|ERROR):|^Ran|OK|FAILED"`
Expected: `test_criteria`, `test_compare`, `test_normalize`, `test_compose`, `test_mutants` OK; failures only in `test_service.py` / `test_service_review.py` tests that asserted partial scores.

- [ ] **Step 3: Update `test_service.py`**

Apply these edits (each replaces the assertions of the named test; everything else in the file stays):

```python
# WrongAnswerTests
    def test_inner_join_is_caught_by_hidden_dataset(self):
        r = grade(task(COUNT_PER_DEPT, hidden=[EMPTY_DEPT]),
                  "SELECT d.name, COUNT(e.id) FROM departments d JOIN employees e "
                  "ON e.dept_id = d.id GROUP BY d.name", sqlite_runner())
        self.assertFalse(r.passed)
        self.assertEqual(r.score, Decimal('0.00'))
        self.assertEqual(r.feedback['failed_datasets'][0]['name'], 'порожній відділ')
        self.assertEqual(r.feedback['passed_count'], r.feedback['total'] - 1)

    def test_wrong_rows_earn_partial_credit_but_never_pass(self):   # rename: test_wrong_rows_score_zero
        r = grade(task('SELECT name FROM employees WHERE salary > 5000'),
                  'SELECT name FROM employees', sqlite_runner())
        self.assertFalse(r.passed)
        self.assertEqual(r.score, Decimal('0.00'))
        self.assertIn('Зайві рядки', r.feedback['hints'][0])

    def test_column_count_mismatch_scores_zero(self):
        r = grade(task('SELECT name, salary FROM employees'), 'SELECT name FROM employees',
                  sqlite_runner())
        self.assertEqual(r.score, Decimal('0.00'))
        self.assertEqual(r.feedback['criteria'][1]['id'], 'columns')
        self.assertFalse(r.feedback['criteria'][1]['passed'])

# HardcodeTests.test_constant_answer_scores_zero: keep; add
        self.assertEqual([c['id'] for c in r.feedback['criteria'] if not c['passed']], ['reads_data'])
# HardcodeTests.test_hardcode_is_rejected_before_hidden_datasets_run: hidden datasets now DO run;
# rewrite to assert the dataset criteria fail on their own data:
    def test_hardcode_also_fails_hidden_datasets(self):
        r = grade(task('SELECT name FROM departments', hidden=[EMPTY_DEPT]),
                  "SELECT 'Розробка' UNION ALL SELECT 'Аналітика' UNION ALL SELECT 'Підтримка'",
                  sqlite_runner())
        ids = {c['id']: c['passed'] for c in r.feedback['criteria']}
        self.assertFalse(ids['reads_data'])
        self.assertFalse(ids['dataset:1'])

# OrderingTests
    def test_order_by_in_reference_makes_order_graded(self):
        r = grade(task('SELECT name FROM employees ORDER BY salary DESC'),
                  'SELECT name FROM employees ORDER BY salary', sqlite_runner())
        self.assertFalse(r.passed)
        self.assertEqual(r.score, Decimal('0.00'))
        self.assertEqual(r.feedback['passed_count'], r.feedback['total'] - 1)
    def test_wrong_rows_fail_order_with_reason(self):   # was test_wrong_rows_do_not_also_lose_order_points
        r = grade(task('SELECT name FROM employees ORDER BY salary DESC'),
                  'SELECT name FROM employees WHERE salary > 5000 ORDER BY salary DESC',
                  sqlite_runner())
        order = next(c for c in r.feedback['criteria'] if c['id'] == 'order')
        self.assertEqual(order['detail'], 'Спершу виправте набір рядків.')
        self.assertEqual(r.score, Decimal('0.00'))

# StructureTests.test_required_construct_missing: score is 0.00 now; message check stays on hints.
# ReferenceModesTests.test_free_exercise_without_any_reference_passes_on_execution:
#   use 'SELECT name FROM employees' as the answer (constant 'SELECT 1' now fails reads_data).
# TruncationTests.test_sqlite_cannot_grade_a_truncated_result: assert hints[0] == MSG['truncated'].
# InDatabaseDifferenceTests.test_hidden_datasets_use_one_diff_call_each_on_postgres: unchanged
#   (one PURPOSE_DIFF call per dataset still holds).
# DmlTests: same expectations (passed / not passed), scores 100.00 / 0.00.
# ScoreShapeTests.test_max_score_scales_the_result: assert score == Decimal('20.00') for a correct
#   answer with max_score=20 and Decimal('0.00') for a wrong one.
# ScoreShapeTests.test_feedback_has_frontend_fields: add 'criteria', 'passed_count', 'total',
#   'threshold' to the asserted key set.
```

- [ ] **Step 4: Update `test_service_review.py`**

- `PartialCreditTests.test_dumping_the_whole_table_earns_at_most_half` → rename `test_dumping_the_whole_table_scores_zero`, assert `score == Decimal('0.00')` and that `precise` is the failed criterion.
- `TimeoutTests.test_hidden_budget_stops_checking_and_does_not_pass`: patch `grading.criteria.HIDDEN_BUDGET_SECONDS` instead of `grading.service.HIDDEN_BUDGET_SECONDS`; assert the second dataset's detail is `MSG['budget']`.
- `TimeoutTests.test_timed_out_difference_is_a_failure_without_retry`: unchanged logic (one diff call, no retry) — keep.
- `CompositionRobustnessTests.test_render_failure_falls_back_to_python_comparison`: patch `grading.criteria.build_symmetric_difference` instead of `grading.service.build_symmetric_difference`.
- `DmlLessonExerciseTests.test_select_reference_with_no_result_columns_is_not_a_pass`: now the `columns` criterion fails with `MSG['no_result']`; assert `not r.passed`.

- [ ] **Step 5: Run the grading suite**

Run: `cd backend && .venv/Scripts/python manage.py test grading --settings=config.settings_test`
Expected: OK, no failures. Then run everything: `manage.py test --settings=config.settings_test` — expect failures only in `submissions/test_grading_flow.py` and `sandbox/test_grading_engines.py` score assertions (fixed in Task 7).

---

### Task 6: Model field, migrations, serializers, catalog endpoint

**Files:**
- Modify: `backend/courses/models.py:183-224` (`LessonExercise.criteria`)
- Modify: `backend/assignments/models.py` (`Assignment.criteria`, after `check_datasets`)
- Create: `backend/courses/migrations/0015_lessonexercise_criteria.py`, `backend/assignments/migrations/0005_assignment_criteria.py` (via `makemigrations`)
- Modify: `backend/courses/serializers.py` (`LessonExerciseSerializer`, `EXERCISE_SOLUTION_FIELDS`, `LessonDetailSerializer.to_representation`)
- Modify: `backend/assignments/serializers.py` (Detail/Create/Instructor)
- Create: `backend/grading/views.py` (replace stub), `backend/grading/urls.py`
- Modify: `backend/config/urls.py` (add `path('api/grading/', include('grading.urls'))`)
- Test: `backend/courses/test_criteria_api.py`

**Interfaces:**
- Produces `courses.serializers.criteria_task(db_type, data) -> GradingTask` (shared helper used by both apps' serializers), `validate_criteria_value(task, value)` raising `serializers.ValidationError`.
- API: `GET /api/grading/criteria/` → `[{id, name, description, kinds}]`.
- Exercise/assignment representation for students gains `criteria_summary: {criteria: [{id, name}], total, threshold}`; instructors additionally see `criteria`.

- [ ] **Step 1: Write the failing API tests**

`backend/courses/test_criteria_api.py`:

```python
"""Instructor-configured criteria through the REST API."""

from rest_framework import status
from rest_framework.test import APITestCase

from courses.models import Course, Enrollment, Lesson, Module
from users.models import User

SCHEMA = 'CREATE TABLE t (a INTEGER, b TEXT);'
SEED = "INSERT INTO t VALUES (1,'x'),(2,'y');"


class CriteriaApiTests(APITestCase):
    def setUp(self):
        self.instructor = User.objects.create_user(email='i@test.com', password='x',
                                                   role=User.Role.INSTRUCTOR)
        self.student = User.objects.create_user(email='s@test.com', password='x',
                                                role=User.Role.STUDENT)
        self.course = Course.objects.create(title='C', instructor=self.instructor,
                                            database_type='sqlite', is_published=True)
        Enrollment.objects.create(student=self.student, course=self.course)
        self.module = Module.objects.create(course=self.course, title='M', is_published=True)
        self.client.force_authenticate(self.instructor)
        resp = self.client.post(f'/api/courses/{self.course.id}/datasets/', {
            'name': 'D', 'database_type': 'sqlite', 'schema_sql': SCHEMA, 'seed_sql': SEED,
        }, format='json')
        self.dataset_id = resp.data['id']

    def lesson_payload(self, exercise):
        return {'title': 'L', 'lesson_type': 'practice', 'module_id': str(self.module.id),
                'is_published': True, 'exercises': [dict(title='E', dataset_id=self.dataset_id,
                                                         **exercise)]}

    def create_lesson(self, exercise):
        return self.client.post(f'/api/courses/{self.course.id}/lessons/',
                                self.lesson_payload(exercise), format='json')

    def test_catalog_lists_general_criteria(self):
        resp = self.client.get('/api/grading/criteria/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data[0]['id'], 'execution')
        self.assertEqual(len(resp.data), 8)

    def test_catalog_requires_login(self):
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get('/api/grading/criteria/').status_code, 401)

    def test_criteria_are_saved_normalized(self):
        resp = self.create_lesson({'expected_query': 'SELECT a FROM t ORDER BY a',
                                   'criteria': {'enabled': ['precise', 'order'], 'threshold': 2}})
        self.assertEqual(resp.status_code, 201, resp.data)
        exercise = Lesson.objects.get(title='L').exercises.first()
        self.assertEqual(exercise.criteria, {'enabled': ['execution', 'precise', 'order'],
                                             'threshold': 2})

    def test_unknown_criterion_is_rejected(self):
        resp = self.create_lesson({'expected_query': 'SELECT a FROM t',
                                   'criteria': {'enabled': ['magic']}})
        self.assertEqual(resp.status_code, 400)
        self.assertIn('Невідомий критерій', str(resp.data))

    def test_order_without_order_by_is_rejected(self):
        resp = self.create_lesson({'expected_query': 'SELECT a FROM t',
                                   'criteria': {'enabled': ['order']}})
        self.assertEqual(resp.status_code, 400)
        self.assertIn('ORDER BY', str(resp.data))

    def test_negative_threshold_is_rejected(self):
        resp = self.create_lesson({'expected_query': 'SELECT a FROM t',
                                   'criteria': {'threshold': -1}})
        self.assertEqual(resp.status_code, 400)

    def test_student_gets_summary_but_not_config(self):
        self.create_lesson({'expected_query': 'SELECT a FROM t ORDER BY a',
                            'required_keywords': ['ORDER BY'],
                            'criteria': {'enabled': ['complete', 'precise'], 'threshold': 3}})
        lesson = Lesson.objects.get(title='L')
        self.client.force_authenticate(self.student)
        resp = self.client.get(f'/api/courses/{self.course.id}/lessons/{lesson.id}/')
        exercise = resp.data['exercises'][0]
        self.assertNotIn('criteria', exercise)
        self.assertNotIn('expected_query', exercise)
        self.assertEqual(exercise['criteria_summary'], {
            'criteria': [{'id': 'execution', 'name': 'Запит виконується'},
                         {'id': 'complete', 'name': 'Усі потрібні рядки є'},
                         {'id': 'precise', 'name': 'Немає зайвих рядків'},
                         {'id': 'require:ORDER BY', 'name': 'Використано ORDER BY'}],
            'total': 4, 'threshold': 3})

    def test_default_summary_for_an_unconfigured_exercise(self):
        self.create_lesson({'expected_query': 'SELECT a FROM t'})
        lesson = Lesson.objects.get(title='L')
        self.client.force_authenticate(self.student)
        resp = self.client.get(f'/api/courses/{self.course.id}/lessons/{lesson.id}/')
        summary = resp.data['exercises'][0]['criteria_summary']
        self.assertEqual([c['id'] for c in summary['criteria']],
                         ['execution', 'columns', 'complete', 'precise', 'reads_data'])
        self.assertEqual(summary['threshold'], 5)

    def test_instructor_sees_both(self):
        self.create_lesson({'expected_query': 'SELECT a FROM t',
                            'criteria': {'enabled': ['complete'], 'threshold': 1}})
        lesson = Lesson.objects.get(title='L')
        resp = self.client.get(f'/api/courses/{self.course.id}/lessons/{lesson.id}/')
        exercise = resp.data['exercises'][0]
        self.assertEqual(exercise['criteria'], {'enabled': ['execution', 'complete'], 'threshold': 1})
        self.assertIn('criteria_summary', exercise)

    def test_assignment_criteria_round_trip(self):
        resp = self.client.post(f'/api/courses/{self.course.id}/assignments/', {
            'title': 'A', 'description': 'd', 'query_type': 'select', 'difficulty': 'easy',
            'dataset': self.dataset_id, 'expected_query': 'SELECT a FROM t',
            'criteria': {'enabled': ['columns'], 'threshold': 9},
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.client.force_authenticate(self.student)
        detail = self.client.get(f'/api/courses/{self.course.id}/assignments/{resp.data["id"]}/')
        self.assertNotIn('criteria', detail.data)
        self.assertEqual(detail.data['criteria_summary']['threshold'], 2)   # clamped to total
```

- [ ] **Step 2: Run to see them fail**

Run: `cd backend && .venv/Scripts/python manage.py test courses.test_criteria_api --settings=config.settings_test`
Expected: 404s / missing fields.

- [ ] **Step 3: Model fields and migrations**

`courses/models.py` after `check_datasets` in `LessonExercise`:

```python
    criteria = models.JSONField(
        default=dict,
        blank=True,
        help_text='Grading criteria chosen by the instructor: '
                  '{"enabled": [...general criterion ids...], "threshold": N}; empty = defaults',
    )
```

Same field on `Assignment` (after `check_datasets`). Then:
`cd backend && .venv/Scripts/python manage.py makemigrations courses assignments --settings=config.settings_test -n criteria` and apply to the dev DB: `DB_HOST=127.0.0.1 DB_PORT=5433 .venv/Scripts/python manage.py migrate` (Docker `db` container must be running).

- [ ] **Step 4: Serializer support**

In `courses/serializers.py`, below `validate_check_datasets_value`:

```python
def criteria_task(db_type, data):
    """A GradingTask built from serializer data, enough for criteria validation and summaries."""
    from grading.runner import build_task
    return build_task(
        db_type or 'sqlite',
        reference_query=data.get('expected_query') or '',
        dataset=None,
        check_datasets=data.get('check_datasets') or [],
        required_keywords=data.get('required_keywords') or [],
        forbidden_keywords=data.get('forbidden_keywords') or [],
        order_matters=bool(data.get('order_matters')),
        expected_result=data.get('expected_result'),
        criteria=data.get('criteria'),
    )


def validate_criteria_value(task, value):
    from grading.criteria import validate_config
    try:
        return validate_config(task, value)
    except ValueError as err:
        raise serializers.ValidationError(str(err))


def criteria_summary(db_type, instance):
    from grading.criteria import describe
    data = {
        'expected_query': instance.expected_query,
        'check_datasets': instance.check_datasets,
        'required_keywords': instance.required_keywords,
        'forbidden_keywords': instance.forbidden_keywords,
        'order_matters': instance.order_matters,
        'expected_result': instance.expected_result,
        'criteria': instance.criteria,
    }
    return describe(criteria_task(db_type, data))
```

`LessonExerciseSerializer`:
- add `'criteria'` to `fields` and `criteria_summary = serializers.SerializerMethodField()` (+ in `fields`);
- `get_criteria_summary(self, obj)`: `return criteria_summary(self._db_type(), obj)`;
- `_db_type(self)`: `course = self.context.get('course')`; if none and `self.root.instance` is a `Lesson`, use `self.root.instance.course`; return `course.database_type if course else 'sqlite'`;
- object-level `validate(self, attrs)`: merge `attrs` over `self.instance` fields when updating (`_sync_exercises` passes dicts, so the nested serializer has no instance; merging over attrs only is enough because the frontend always sends the full exercise); then `attrs['criteria'] = validate_criteria_value(criteria_task(self._db_type(), attrs), attrs.get('criteria'))` and return attrs.
- `EXERCISE_SOLUTION_FIELDS = ('expected_query', 'expected_result', 'check_datasets', 'criteria')`.

Lesson views must put the course into the serializer context for detail/update as they already do for create (`validate_module_id` relies on `context['course']`): check `LessonViewSet.get_serializer_context` in `courses/views.py`; if it only sets `course` for create, make it always set `context['course'] = Course.objects.filter(id=self.kwargs.get('course_pk')).first()`.

`assignments/serializers.py`:
- `AssignmentDetailSerializer`: add `criteria_summary = serializers.SerializerMethodField()` to fields; `get_criteria_summary(self, obj)` → `criteria_summary(obj.course.database_type, obj)` (import from `courses.serializers`).
- `AssignmentCreateSerializer`: add `'criteria'` to fields; `validate(self, attrs)`: `merged = {f: getattr(self.instance, f) for f in ('expected_query','check_datasets','required_keywords','forbidden_keywords','order_matters','expected_result')} if self.instance else {}`; `merged.update(attrs)`; db_type from `self.context['view'].kwargs['course_pk']` course (or `self.instance.course`); `attrs['criteria'] = validate_criteria_value(criteria_task(db_type, merged), attrs.get('criteria', merged.get('criteria')))`; return attrs.
- `AssignmentInstructorSerializer.Meta.fields += ['criteria']`.

- [ ] **Step 5: Catalog endpoint**

`grading/views.py`:

```python
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .criteria import catalog_payload


class CriteriaCatalogView(APIView):
    """General criteria an instructor can enable for an exercise."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(catalog_payload())
```

`grading/urls.py`:

```python
from django.urls import path

from .views import CriteriaCatalogView

urlpatterns = [
    path('criteria/', CriteriaCatalogView.as_view(), name='grading-criteria'),
]
```

`config/urls.py`: add `path('api/grading/', include('grading.urls')),` next to the sandbox include.

- [ ] **Step 6: Run the API tests, then the full suite**

Run: `cd backend && .venv/Scripts/python manage.py test courses.test_criteria_api --settings=config.settings_test` → OK.
Run: `manage.py test courses submissions assignments users --settings=config.settings_test` → only the score assertions in `submissions/test_grading_flow.py` may fail (Task 7).

---

### Task 7: Submission view: pass criteria, store JSON-safe results; update flow and engine tests

**Files:**
- Create: `backend/submissions/storage.py`
- Modify: `backend/submissions/views.py:95-115, 140-160, 220-260`
- Create: `backend/submissions/test_result_storage.py`
- Modify: `backend/submissions/test_grading_flow.py`
- Modify: `backend/sandbox/test_grading_engines.py`

**Interfaces:**
- Produces `submissions.storage.json_safe(value)`: Decimal→int/float, date/datetime/time→ISO string, bytes→hex, dict/list recursively, other unknown→`str`.

- [ ] **Step 1: Write the failing storage tests**

`backend/submissions/test_result_storage.py`:

```python
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

    def test_result_is_json_serializable(self):
        payload = json_safe({'rows': [[Decimal('1'), dt.date(2020, 5, 5), None, True, 'x']]})
        json.dumps(payload)   # must not raise
```

And in `test_grading_flow.py` add a regression test that goes through the view with a fake sandbox returning Decimals (SQLite itself never does):

```python
    def test_result_with_decimal_and_dates_is_stored(self):
        from unittest import mock
        import datetime as dt
        from decimal import Decimal
        from grading.service import Execution

        def fake_runner(db_type, timeout, **kw):
            def run(sql, dataset, purpose):
                return Execution(True, ['name', 'salary', 'hired'],
                                 [['Іваненко', Decimal('6000.00'), dt.date(2021, 3, 15)]])
            return run

        with mock.patch('submissions.views.make_runner', fake_runner):
            resp = self.submit('SELECT name, salary, hired FROM employees', self.exercises[1])
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        self.assertEqual(resp.data['result']['rows'][0], ['Іваненко', 6000, '2021-03-15'])
```

- [ ] **Step 2: Run to see them fail**

Run: `cd backend && .venv/Scripts/python manage.py test submissions.test_result_storage submissions.test_grading_flow.GradingFlowTestCase.test_result_with_decimal_and_dates_is_stored --settings=config.settings_test`
Expected: ImportError / 500.

- [ ] **Step 3: Implement `storage.py` and wire the view**

`backend/submissions/storage.py`:

```python
"""Make engine results safe to store in a JSONField."""

import datetime as dt
from decimal import Decimal


def json_safe(value):
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral_value() else float(value)
    if isinstance(value, (dt.datetime, dt.date, dt.time)):
        return value.isoformat()
    if isinstance(value, (bytes, bytearray, memoryview)):
        return bytes(value).hex()
    if isinstance(value, dict):
        return {str(k): json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [json_safe(v) for v in value]
    return str(value)
```

`submissions/views.py`:
- in both branches read `criteria = assignment.criteria or {}` / `criteria = exercise.criteria or {}`;
- pass `criteria=criteria` to `build_task(...)`;
- when storing the result: `'columns': json_safe(execution.columns), 'rows': json_safe(execution.rows)`;
- `submission.feedback = json_safe(graded.feedback)` (hints are strings already; this is belt and braces).

- [ ] **Step 4: Update `test_grading_flow.py` expectations**

- `test_inner_join_is_caught_by_hidden_dataset`: score `Decimal('0.00')`; `feedback['passed_count'] == feedback['total'] - 1`; `failed_datasets[0]['name'] == 'порожній відділ'`.
- `test_hardcoded_answer_scores_zero`: add `self.assertFalse(next(c['passed'] for c in resp.data['feedback']['criteria'] if c['id'] == 'reads_data'))`.
- `test_required_keyword_is_enforced`: score 0, `'LEFT JOIN' in feedback['keywords_missing']`.
- `test_wrong_sort_order_is_not_correct`: score 0 and `is_correct False`; `test_correct_sort_order_passes`: 100.
- `test_user_result_tracks_best_score_and_completion`: wrong attempt gives `best_score 0`, correct gives 100.
- `test_lesson_is_completed_after_all_exercises_are_solved`: unchanged.
- `test_update_exercise_in_lesson_is_graded_by_execution`: `feedback['mode'] == 'execution'`, criteria ids `['execution', 'state']`.
- Add:

```python
    def test_instructor_threshold_lets_one_criterion_fail(self):
        self.as_instructor()
        lesson = self.create_lesson('Поріг', exercises=[{
            'title': 'За спаданням', 'expected_query': BY_SALARY_DESC, 'dataset_id': self.dataset_id,
            'criteria': {'enabled': ['columns', 'complete', 'precise', 'order'], 'threshold': 4},
        }])
        exercise = lesson.exercises.first()
        self.as_student()
        resp = self.submit('SELECT name FROM employees ORDER BY salary', exercise=exercise,
                           lesson=lesson)
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        fb = resp.data['feedback']
        self.assertEqual((fb['passed_count'], fb['total'], fb['threshold']), (4, 5, 4))
        self.assertTrue(resp.data['is_correct'])
        self.assertEqual(Decimal(resp.data['score']), Decimal('100.00'))
        self.assertEqual([c['id'] for c in fb['criteria'] if not c['passed']], ['order'])

    def test_threshold_not_met_scores_zero(self):
        self.as_instructor()
        lesson = self.create_lesson('Поріг 2', exercises=[{
            'title': 'За спаданням', 'expected_query': BY_SALARY_DESC, 'dataset_id': self.dataset_id,
            'criteria': {'enabled': ['columns', 'complete', 'precise', 'order'], 'threshold': 5},
        }])
        exercise = lesson.exercises.first()
        self.as_student()
        resp = self.submit('SELECT name FROM employees ORDER BY salary', exercise=exercise,
                           lesson=lesson)
        self.assertFalse(resp.data['is_correct'])
        self.assertEqual(Decimal(resp.data['score']), Decimal('0.00'))
        self.assertIn('потрібно 5', resp.data['feedback']['message'])

    def test_lesson_score_is_the_sum_of_exercise_scores(self):
        self.submit(COUNT_PER_DEPT, self.exercises[0])
        self.submit(BY_SALARY_DESC, self.exercises[1])
        resp = self.client.get(f'/api/courses/{self.course_id}/lessons/')
        lesson = next(l for l in resp.data['results'] if l['id'] == str(self.lesson.id))
        self.assertEqual(Decimal(str(lesson['user_best_score'])), Decimal('200.00'))
```

`AssignmentGradingTestCase.test_update_assignment_compares_affected_rows`: the assignment path now also uses `make_sequence_runner`, so a matching UPDATE passes and a wrong one gives `feedback['criteria'][1]['id'] == 'state'` failed; keep the pass/fail expectations.

- [ ] **Step 5: Update `sandbox/test_grading_engines.py`**

Scores: every `assertEqual(r.score, Decimal('xx.xx'))` other than `100.00`/`0.00` becomes `0.00`; `assertFalse(r.passed)` stays. Add to `SqlEngineMixin`:

```python
    def test_numeric_and_date_columns_are_stored(self):
        """Full view path: NUMERIC and DATE values must be storable (used to be HTTP 500)."""
        from submissions.storage import json_safe
        r = self.grade('SELECT name, salary FROM employees WHERE salary > 5000',
                       'SELECT name, salary FROM employees WHERE salary > 5000')
        self.assertTrue(r.passed, r.feedback)
        import json
        json.dumps(json_safe(r.execution.rows))   # must not raise on Decimal
```

and for `PostgresEngineTests` only, a view-level test using `APIClient` is not possible without the main DB on Postgres; the SQLite flow test from Step 1 covers the view, this covers the real Decimal rows.

- [ ] **Step 6: Run everything**

Run: `cd backend && .venv/Scripts/python manage.py test --settings=config.settings_test`
Expected: OK (expect ~440 tests found, 4 engine classes skipped).
Optional with Docker sandboxes up: `SANDBOX_INTEGRATION=1 SANDBOX_POSTGRESQL_HOST=127.0.0.1 SANDBOX_POSTGRESQL_PORT=55432 SANDBOX_MARIADB_HOST=127.0.0.1 SANDBOX_MARIADB_PORT=53306 SANDBOX_MONGODB_HOST=127.0.0.1 SANDBOX_MONGODB_PORT=57017 SANDBOX_REDIS_HOST=127.0.0.1 SANDBOX_REDIS_PORT=56379 .venv/Scripts/python manage.py test sandbox.test_grading_engines --settings=config.settings_test` → OK on all five engines.

---

### Task 8: Frontend types, API client, hook, zod schema, criteria helpers

**Files:**
- Create: `frontend/src/api/grading.ts`
- Create: `frontend/src/hooks/queries/useGrading.ts`
- Create: `frontend/src/lib/criteria.ts`
- Modify: `frontend/src/types/index.ts:118-138`
- Modify: `frontend/src/api/lessons.ts:13-35` (`LessonExercise`), `frontend/src/api/assignments.ts:4-23`
- Modify: `frontend/src/lib/schemas.ts:49-72` (`exerciseSchema`)

**Interfaces:**
- `types`: `ExerciseCriteria {enabled: string[]; threshold: number}`, `CriteriaSummary {criteria: {id: string; name: string}[]; total: number; threshold: number}`, `CriterionInfo {id: string; name: string; description: string; kinds: ('select'|'dml'|'nosql')[]}`, `CriterionVerdict {id: string; name: string; passed: boolean; detail: string}`; `SubmissionFeedback` += `criteria?: CriterionVerdict[]; passed_count?: number; total?: number; threshold?: number`.
- `api/grading.ts`: `gradingApi.getCriteriaCatalog(): Promise<CriterionInfo[]>` (`GET /grading/criteria/`).
- `hooks/queries/useGrading.ts`: `useCriteriaCatalog()` (queryKey `['grading','criteria']`, `staleTime: Infinity`).
- `lib/criteria.ts`: `detectKind(expectedQuery: string, dbType: string): 'select'|'dml'|'nosql'`; `hasOrderBy(expectedQuery: string): boolean` (regex `/\border\s+by\b/i`); `applicableCriteria(catalog, kind, expectedQuery, hasReference): CriterionInfo[]`; `defaultCriteria(applicable: CriterionInfo[]): ExerciseCriteria` (all applicable ids except `column_names`, threshold = ids.length + 0 — derived are added by the editor); `derivedCriteria(exercise): {id: string; name: string; hint: string}[]`.

- [ ] **Step 1: Types and API**

```ts
// types/index.ts (append near SubmissionCheck)
export interface CriterionVerdict { id: string; name: string; passed: boolean; detail: string }
export interface ExerciseCriteria { enabled: string[]; threshold: number }
export interface CriteriaSummary { criteria: { id: string; name: string }[]; total: number; threshold: number }
export type CriterionKind = 'select' | 'dml' | 'nosql';
export interface CriterionInfo { id: string; name: string; description: string; kinds: CriterionKind[] }
// SubmissionFeedback: add
//   criteria?: CriterionVerdict[]; passed_count?: number; total?: number; threshold?: number;
```

```ts
// api/grading.ts
import { apiClient } from './client';
import type { CriterionInfo } from '@/types';

const gradingApi = {
  getCriteriaCatalog: async () => {
    const response = await apiClient.get<CriterionInfo[]>('/grading/criteria/');
    return response.data;
  },
};
export default gradingApi;
```

```ts
// hooks/queries/useGrading.ts
import { useQuery } from '@tanstack/react-query';
import gradingApi from '@/api/grading';

export function useCriteriaCatalog() {
  return useQuery({ queryKey: ['grading', 'criteria'], queryFn: gradingApi.getCriteriaCatalog, staleTime: Infinity });
}
```

`api/lessons.ts` `LessonExercise`: add `criteria?: ExerciseCriteria; criteria_summary?: CriteriaSummary;` (import types). `api/assignments.ts` `CreateAssignmentData`: add `criteria?: ExerciseCriteria;`; the assignment detail type used by `AssignmentPage` (check `types/index.ts` `Assignment` interface) gets `criteria_summary?: CriteriaSummary`.

- [ ] **Step 2: zod schema**

In `exerciseSchema` add:

```ts
  criteria: z
    .object({ enabled: z.array(z.string()).default([]), threshold: z.number().int().min(0).default(0) })
    .default({ enabled: [], threshold: 0 }),
```

Keep `order_matters` in the schema (the backend still accepts it) but the form no longer renders it.

- [ ] **Step 3: `lib/criteria.ts`**

```ts
import type { CriterionInfo, CriterionKind, ExerciseCriteria } from '@/types';

const DML = /^\s*(insert|update|delete|create|alter|drop|truncate|replace)\b/i;

export function detectKind(expectedQuery: string, dbType: string): CriterionKind {
  if (dbType === 'mongodb' || dbType === 'redis') return 'nosql';
  return DML.test(expectedQuery) ? 'dml' : 'select';
}

export function hasOrderBy(expectedQuery: string): boolean {
  return /\border\s+by\b/i.test(expectedQuery);
}

export function applicableCriteria(
  catalog: CriterionInfo[], kind: CriterionKind, expectedQuery: string, hasReference: boolean,
): CriterionInfo[] {
  const resultIds = new Set(['columns', 'column_names', 'complete', 'precise', 'order']);
  return catalog.filter((c) => {
    if (!c.kinds.includes(kind)) return false;
    if (resultIds.has(c.id) && !hasReference) return false;
    if (c.id === 'order' && kind !== 'nosql' && !hasOrderBy(expectedQuery)) return false;
    return true;
  });
}

export function defaultCriteria(applicable: CriterionInfo[]): ExerciseCriteria {
  const enabled = applicable.map((c) => c.id).filter((id) => id !== 'column_names');
  return { enabled, threshold: 0 };
}

export interface DerivedCriterion { id: string; name: string; hint: string }

export function derivedCriteria(exercise: {
  check_datasets?: { name: string }[]; required_keywords?: string[]; forbidden_keywords?: string[]; expected_query?: string;
}): DerivedCriterion[] {
  const out: DerivedCriterion[] = [];
  if (exercise.expected_query?.trim()) {
    (exercise.check_datasets ?? []).forEach((ds, i) =>
      out.push({ id: `dataset:${i + 1}`, name: `Контрольний набір №${i + 1}`, hint: ds.name || '' }));
  }
  (exercise.required_keywords ?? []).filter((k) => k.trim()).forEach((k) =>
    out.push({ id: `require:${k.trim()}`, name: `Використано ${k.trim()}`, hint: '' }));
  (exercise.forbidden_keywords ?? []).filter((k) => k.trim()).forEach((k) =>
    out.push({ id: `forbid:${k.trim()}`, name: `Не використано ${k.trim()}`, hint: '' }));
  return out;
}
```

(`reads_data` for a constant reference and `order_matters` legacy are server-side decisions; the server drops inapplicable ids at grading time, so a stale client choice can never break grading.)

- [ ] **Step 4: Type-check**

Run: `cd frontend && npm run build` → must pass (nothing renders the new code yet).

---

### Task 9: Criteria editor in the lesson form

**Files:**
- Create: `frontend/src/components/grading/CriteriaEditor.tsx`
- Modify: `frontend/src/pages/instructor/LessonFormPage.tsx:38-52` (defaults), `:150-260` (editor), `:370-395` (load existing)

**Interfaces:**
- `CriteriaEditor` props: `{ value: ExerciseCriteria; onChange: (v: ExerciseCriteria) => void; catalog: CriterionInfo[]; kind: CriterionKind; expectedQuery: string; hasReference: boolean; derived: DerivedCriterion[] }`.

- [ ] **Step 1: Component**

```tsx
import { Label } from '@/components/ui/label';
import { Input } from '@/components/ui/input';
import { Switch } from '@/components/ui/switch';
import { applicableCriteria } from '@/lib/criteria';
import type { CriterionInfo, CriterionKind, ExerciseCriteria } from '@/types';
import type { DerivedCriterion } from '@/lib/criteria';

interface Props {
  value: ExerciseCriteria;
  onChange: (v: ExerciseCriteria) => void;
  catalog: CriterionInfo[];
  kind: CriterionKind;
  expectedQuery: string;
  hasReference: boolean;
  derived: DerivedCriterion[];
}

export function CriteriaEditor({ value, onChange, catalog, kind, expectedQuery, hasReference, derived }: Props) {
  const applicable = applicableCriteria(catalog, kind, expectedQuery, hasReference);
  const enabled = new Set(value.enabled.filter((id) => applicable.some((c) => c.id === id)));
  enabled.add('execution');
  const total = enabled.size + derived.length;
  const threshold = value.threshold > 0 && value.threshold <= total ? value.threshold : total;

  function toggle(id: string, on: boolean) {
    const next = new Set(enabled);
    if (on) next.add(id); else next.delete(id);
    next.add('execution');
    const nextTotal = next.size + derived.length;
    onChange({
      enabled: applicable.map((c) => c.id).filter((cid) => next.has(cid)),
      threshold: Math.min(threshold, nextTotal) === nextTotal ? 0 : Math.min(threshold, nextTotal),
    });
  }

  function setThreshold(raw: string) {
    const n = parseInt(raw, 10);
    if (!Number.isFinite(n)) return;
    const clamped = Math.max(1, Math.min(n, total));
    onChange({ enabled: [...enabled], threshold: clamped === total ? 0 : clamped });
  }

  return (
    <div className="space-y-3" data-testid="criteria-editor">
      <div className="space-y-2">
        {applicable.map((c) => (
          <div key={c.id} className="flex items-start gap-3">
            <Switch
              id={`crit-${c.id}`}
              checked={enabled.has(c.id)}
              disabled={c.id === 'execution'}
              onCheckedChange={(on) => toggle(c.id, on)}
              aria-label={c.name}
            />
            <div>
              <Label htmlFor={`crit-${c.id}`}>{c.name}</Label>
              <p className="text-xs text-muted-foreground">{c.description}</p>
            </div>
          </div>
        ))}
      </div>
      {derived.length > 0 && (
        <div className="space-y-1 border-l-2 pl-3">
          {derived.map((d) => (
            <p key={d.id} className="text-sm">
              {d.name}
              {d.hint && <span className="text-muted-foreground"> ({d.hint})</span>}
              <span className="block text-xs text-muted-foreground">Керується списком наборів або ключових слів вище</span>
            </p>
          ))}
        </div>
      )}
      <div className="flex items-center gap-2">
        <Label htmlFor="criteria-threshold">Достатньо</Label>
        <Input id="criteria-threshold" type="number" min={1} max={total} className="w-20"
               value={threshold} onChange={(e) => setThreshold(e.target.value)} />
        <span className="text-sm text-muted-foreground">з {total}</span>
      </div>
    </div>
  );
}
```

Store `threshold: 0` whenever it equals the total: the backend treats 0 as "all", so adding a dataset later keeps "all" semantics; an explicit smaller number is stored as is.

- [ ] **Step 2: Wire into `ExerciseEditor`**

- `newExerciseDefaults`: add `criteria: { enabled: [], threshold: 0 }` (the editor fills the enabled list from the catalog on first render via an effect: `useEffect(() => { if (exercise.criteria.enabled.length === 0 && applicable.length) setValue(..., defaultCriteria(applicable)) }, [applicable ids joined])`).
- Add props `dbType: string` and `catalog: CriterionInfo[]` to `ExerciseEditorProps`; the page loads the catalog once with `useCriteriaCatalog()` and passes `course.database_type` (already known on the page as `course`).
- Below the "Hidden check datasets" block add a section:

```tsx
<div className="space-y-2">
  <Label>Критерії оцінювання</Label>
  <p className="text-xs text-muted-foreground">
    Кожен критерій перевіряється як так/ні. Завдання зараховано, якщо пройдено не менше порога; бал тоді повний, інакше 0.
  </p>
  <CriteriaEditor
    value={exercise?.criteria ?? { enabled: [], threshold: 0 }}
    onChange={(v) => setValue(`exercises.${index}.criteria`, v, { shouldDirty: true })}
    catalog={catalog}
    kind={detectKind(expectedQuery, dbType)}
    expectedQuery={expectedQuery}
    hasReference={Boolean(expectedQuery.trim())}
    derived={derivedCriteria(exercise ?? {})}
  />
</div>
```

- Remove the "Order matters" switch block if present (grep `order_matters` in the JSX; keep the schema field, it is sent as `false`).
- When loading an existing lesson (`reset(...)` at ~line 370-395): `criteria: ex.criteria ?? { enabled: [], threshold: 0 }`.

- [ ] **Step 3: Build and check in the browser**

Run: `cd frontend && npm run build` → OK. Then with backend + frontend running (`DB_HOST=127.0.0.1 DB_PORT=5433 ... manage.py runserver 127.0.0.1:8000 --noreload`, `npm run dev`), as instructor@test.com open an existing lesson: the criteria block shows execution (locked on), columns, complete, precise (+ order when the reference has ORDER BY), the derived rows, and "Достатньо N з M". Toggle one off, set the threshold, save, reload: values persist (check the network response of the lesson GET).

---

### Task 10: Student pages: criteria list before submission, verdict checklist after

**Files:**
- Create: `frontend/src/components/grading/CriteriaChecklist.tsx`
- Modify: `frontend/src/pages/lessons/LessonPage.tsx:95-130` (task card), `:283-310` (feedback block), history rows
- Modify: `frontend/src/pages/assignments/AssignmentPage.tsx` (task card + feedback block)
- Modify: `frontend/src/i18n/locales/uk/lessons.json`, `frontend/src/i18n/locales/en/lessons.json`

**Interfaces:**
- `CriteriaChecklist` props: `{ summary?: CriteriaSummary; feedback?: SubmissionFeedback }` — with only `summary` it renders the upfront list ("Критерії: M, достатньо N" + names); with `feedback` it renders "Пройдено k із M" (+ "потрібно N" when failed) and each verdict with ✓/✗ and detail.

- [ ] **Step 1: i18n keys**

uk `lessons.json` → `page`:
```json
"criteriaTitle": "Критерії оцінювання",
"criteriaCount": "Критеріїв: {{total}}, достатньо {{threshold}}",
"criteriaPassed": "Пройдено {{passed}} із {{total}}",
"criteriaNeeded": "потрібно {{threshold}}",
"criteriaShort": "{{passed}} із {{total}}"
```
en:
```json
"criteriaTitle": "Grading criteria",
"criteriaCount": "Criteria: {{total}}, {{threshold}} required",
"criteriaPassed": "Passed {{passed}} of {{total}}",
"criteriaNeeded": "{{threshold}} required",
"criteriaShort": "{{passed}} of {{total}}"
```

- [ ] **Step 2: Component**

```tsx
import { useTranslation } from 'react-i18next';
import { CheckCircle, XCircle } from 'lucide-react';
import type { CriteriaSummary, SubmissionFeedback } from '@/types';

export function CriteriaChecklist({ summary, feedback }: { summary?: CriteriaSummary; feedback?: SubmissionFeedback }) {
  const { t } = useTranslation('lessons');
  if (feedback?.criteria && feedback.criteria.length > 0) {
    const passed = feedback.passed_count ?? feedback.criteria.filter((c) => c.passed).length;
    const total = feedback.total ?? feedback.criteria.length;
    const threshold = feedback.threshold ?? total;
    const ok = passed >= threshold;
    return (
      <div className="space-y-2" data-testid="criteria-result">
        <p className={`text-sm font-medium ${ok ? 'text-success' : 'text-destructive'}`}>
          {t('page.criteriaPassed', { passed, total })}
          {!ok && <span className="text-muted-foreground">, {t('page.criteriaNeeded', { threshold })}</span>}
        </p>
        <ul className="space-y-1">
          {feedback.criteria.map((c) => (
            <li key={c.id} className="flex items-start gap-2 text-sm">
              {c.passed ? <CheckCircle className="h-4 w-4 mt-0.5 text-success" aria-label="✓" />
                        : <XCircle className="h-4 w-4 mt-0.5 text-destructive" aria-label="✗" />}
              <span>
                {c.name}
                {!c.passed && c.detail && <span className="block text-xs text-muted-foreground">{c.detail}</span>}
              </span>
            </li>
          ))}
        </ul>
      </div>
    );
  }
  if (summary && summary.criteria.length > 0) {
    return (
      <div className="space-y-1" data-testid="criteria-summary">
        <p className="text-sm font-medium">{t('page.criteriaTitle')}</p>
        <p className="text-xs text-muted-foreground">{t('page.criteriaCount', { total: summary.total, threshold: summary.threshold })}</p>
        <ul className="list-disc pl-5 text-sm">{summary.criteria.map((c) => <li key={c.id}>{c.name}</li>)}</ul>
      </div>
    );
  }
  return null;
}
```

If the project has no `text-success` utility, use `text-green-600 dark:text-green-400` (check `badge.tsx` for the success colour already used).

- [ ] **Step 3: LessonPage**

- Task card (`ExercisePanel`, after the description `<p>`): `<div className="mt-4"><CriteriaChecklist summary={exercise.criteria_summary} /></div>`.
- Feedback block (line ~283): replace the `checks` badges block with `<CriteriaChecklist feedback={submission.feedback} />`; keep `message` and `hints` as they are (hints now repeat the failed details; drop the `hints` list when `feedback.criteria` exists to avoid duplication: `{!submission.feedback.criteria && submission.feedback.hints && (...)}`).
- History row: after the score span add `{attempt.feedback?.total ? <span className="text-muted-foreground">{t('page.criteriaShort', { passed: attempt.feedback.passed_count, total: attempt.feedback.total })}</span> : null}`.

- [ ] **Step 4: AssignmentPage**

Same two insertions: `summary={assignment.criteria_summary}` under the instructions, and `<CriteriaChecklist feedback={currentSubmission.feedback} />` replacing the keywords lines (keep `message`; hide `hints`/keywords when `feedback.criteria` exists).

- [ ] **Step 5: Build and browser check**

Run: `cd frontend && npm run build` → OK. As student@test.com open a practice lesson: the task card lists the criteria and the threshold; submit a wrong-order answer on an ORDER BY exercise: "Пройдено 4 із 5, потрібно 5", `Порядок рядків` ✗ with "Рядки правильні, але порядок інший.", score 0; submit the correct one: "Пройдено 5 із 5", score 100; history shows "4 із 5" and "5 із 5".

---

### Task 11: Documentation and final verification

**Files:**
- Modify: `GRADING_ALGORITHM.md` (overview, Part I §10, Part II items 8-9, "Рекомендований порядок")
- Modify: `C:\Users\grytc\.claude\projects\D--VIBE-MAX\memory\project_sql_learning_platform.md` (score model paragraph, open-bug paragraph)

- [ ] **Step 1: Rewrite the scoring sections of `GRADING_ALGORITHM.md`**

Overview "Як рахується бал": replace the weighted table with: list of criteria, "кожен критерій так/ні", "зараховано, якщо пройдено не менше порога N з M, який задає викладач; бал повний або 0", default = all applicable except column names, threshold = all. Part I §10: replace with the criteria catalog table (§3 of the spec), dependency rules (§5.3), feedback shape, and a worked example "6 із 7". Part II: delete items 8 and 9, renumber, add to "Обмеження" that partial credit no longer exists by design and that a weight per criterion is a possible extension. Part III row 6 (рубрика): status "замінено на бінарні критерії з порогом".

- [ ] **Step 2: Full verification**

Run: `cd backend && .venv/Scripts/python manage.py test --settings=config.settings_test` → OK.
Run: `cd frontend && npm run build` → OK.
Restart the backend (`--noreload`) and do the browser pass from Tasks 9 and 10 once more end-to-end: instructor edits criteria → student sees them → submits → checklist and score → instructor's student progress shows the same best score.

- [ ] **Step 3: Memory**

Replace the "Score = max_score * weighted mean..." paragraph in the memory file with the criteria model (ids, threshold, 100/0) and mark the NUMERIC/DATE bug as fixed (Task 7). Keep the demo-kit note.
