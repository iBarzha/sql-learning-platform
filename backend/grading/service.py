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
          run_sequence: Optional[SequenceRunFn] = None, *,
          reveal_rows: bool = True) -> GradeResult:
    """`reveal_rows=False` keeps the reference's values out of the feedback."""
    result = evaluate(task, student_query, run, run_sequence, reveal_rows=reveal_rows)
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
    if diff is not None and diff.kind == cmp.KIND_ROWS and ctx.reveal_rows:
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
        result_match = (bool(by_id.get('complete', {}).get('passed'))
                        and bool(by_id.get('precise', {}).get('passed')))

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
        'keywords_missing': [i['id'][len('require:'):] for i in failed
                             if i['id'].startswith('require:')],
        'forbidden_used': [i['id'][len('forbid:'):] for i in failed
                           if i['id'].startswith('forbid:')],
        'failed_datasets': failed_datasets,
        'datasets_checked': 1 + datasets_checked,
        'missing_rows': missing_rows,
        'extra_rows': extra_rows,
    }
