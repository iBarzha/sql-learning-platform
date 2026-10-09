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
# Runs several statements on one seeded sandbox and returns one Execution per statement.
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
