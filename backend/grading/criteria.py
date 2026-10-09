"""Binary grading criteria.

Each criterion is one yes/no question about a submission. The instructor chooses which
questions count for an exercise and how many "yes" answers are enough (`describe`);
`evaluate` asks every selected question. Scoring is a single comparison,
passed_count >= threshold.
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from functools import cached_property
from typing import Any, Callable, Optional, Sequence

from . import compare as cmp
from .compose import (
    STATEMENT_DML,
    STATEMENT_MULTIPLE,
    STATEMENT_SELECT,
    QueryShapeError,
    build_symmetric_difference,
    classify_statement,
    constructs,
    created_table,
    dialect_for,
    has_order_by,
    is_constant_query,
    parse_query,
    parse_statement,
    reads_data,
    select_all_sql,
    supports_except_all,
    tables_in_schema,
)
from .normalize import canonical_json
from .types import (
    NOSQL_TYPES,
    PURPOSE_DIFF,
    PURPOSE_REFERENCE,
    PURPOSE_STUDENT,
    CheckDataset,
    Execution,
    GradingTask,
    RunFn,
    SequenceRunFn,
)

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
    if not task.is_select_task and task.reference_query and reference_kind != STATEMENT_SELECT:
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
    ids = [cid for cid in applicable_ids(task) if cid not in DEFAULT_OFF]
    # NoSQL answers have no ORDER BY to signal that order matters; Redis sets and hashes
    # come back in arbitrary order, so grading it must be the instructor's explicit choice.
    if task.db_type in NOSQL_TYPES and not task.order_matters:
        ids = [cid for cid in ids if cid != 'order']
    return ids


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
    # Data-changing tasks are graded by table state on the primary data only; a hidden
    # dataset would compare two empty result sets and pass any statement that runs.
    if task.reference_query and task_kind(task) != KIND_DML:
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
    if not enabled:
        # "Nothing chosen" keeps meaning "server defaults", exactly as the form shows it.
        return {'enabled': [], 'threshold': threshold} if threshold else {}
    wanted = set(enabled) | ALWAYS_ON
    return {'enabled': [cid for cid in applicable if cid in wanted], 'threshold': threshold}


def normalize_config(task: GradingTask, config: Any) -> dict:
    """Like `validate_config`, but drops ids that no longer apply instead of failing.

    Used when the instructor edits the reference without touching the criteria: the
    stored choice is kept as far as it still makes sense, mirroring `resolve_config`.
    """
    if not isinstance(config, dict):
        return {}
    chosen = [cid for cid in (config.get('enabled') or []) if isinstance(cid, str)]
    threshold = _threshold_of(config)
    if not chosen:
        return {'enabled': [], 'threshold': threshold} if threshold else {}
    wanted = set(chosen) | ALWAYS_ON
    return {'enabled': [cid for cid in applicable_ids(task) if cid in wanted],
            'threshold': threshold}


def catalog_payload() -> list[dict]:
    return [{'id': s.id, 'name': s.name, 'description': s.description, 'kinds': list(s.kinds)}
            for s in GENERAL]


# ── evaluation ──────────────────────────────────────────────────────────────

# Hidden datasets each cost a full reseed; stop checking when this is exhausted so a
# slow query cannot hold an HTTP request for minutes.
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

    truncated_but_decided = False

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
        student = self.run_sequence([self.student_query, *selects], self.task.primary,
                                    PURPOSE_STUDENT)
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
        if self.reference_exec is None:
            return []
        return prepare_rows(self.task.db_type, self.reference_exec.rows)

    @cached_property
    def diff(self) -> Optional[cmp.Diff]:
        """Unordered diff on the primary dataset; None when there is nothing to compare."""
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
        if (self.student_node is None or not task.reference_query
                or not supports_except_all(task.db_type)):
            return None
        try:
            sql = build_symmetric_difference(self.student_query, task.reference_query, task.db_type)
        except Exception:  # noqa: BLE001 - any composition failure means "compare in Python"
            return None
        result = self.run(sql, dataset, PURPOSE_DIFF)
        if result.success:
            return len(result.rows) == 0
        if result.timed_out:
            # Re-running the student's query separately would only time out again.
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
                        student_truncated=student.truncated,
                        expected_truncated=reference.truncated)
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


# ── criterion evaluators ───────────────────────────────────────────────────

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
    expected = ctx.reference_exec.columns
    actual = ctx.student_exec.columns
    for position, (e, a) in enumerate(zip(expected, actual), start=1):
        if e.strip().lower() != a.strip().lower():
            return Verdict(False, f'Стовпець {position}: очікується {e}, отримано {a}.')
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
    if not ctx.uses_table_state:
        # Legacy fallback: no sequence runner or no readable schema.
        reference = ctx.reference_exec
        if reference is None:
            return Verdict(True)
        same = reference.affected_rows == ctx.student_exec.affected_rows
        if same:
            return Verdict(True)
        return Verdict(False, f'Змінених рядків: очікується {reference.affected_rows}, '
                              f'отримано {ctx.student_exec.affected_rows}.')
    student_results, reference_results = ctx.dml_runs
    details: list[str] = []
    for index, table in enumerate(ctx.dml_tables, start=1):
        student_state = student_results[index] if index < len(student_results) else None
        reference_state = reference_results[index] if index < len(reference_results) else None
        if reference_state is None or not reference_state.success:
            continue   # the reference cannot see this table either (e.g. it drops it)
        if student_state is None or not student_state.success:
            details.append(f'таблиця {table} недоступна або відсутня')
            continue
        d = cmp.compare(student_state.columns, student_state.rows,
                        reference_state.columns, reference_state.rows)
        if d.equal:
            continue
        if d.kind == cmp.KIND_COLUMN_COUNT:
            details.append(f'таблиця {table}: очікується {d.expected_columns} стовпців, '
                           f'отримано {d.student_columns}')
        else:
            if d.missing:
                details.append(f'таблиця {table}, бракує рядків: {d.describe_missing()}')
            if d.extra:
                details.append(f'таблиця {table}, зайві рядки: {d.describe_extra()}')
    if details:
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
        if ctx.uses(value):
            return Verdict(False, f'Використано заборонене {value}.')
        return Verdict(True)
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
