"""Multiset comparison of query results.

Mirrors what `(A EXCEPT ALL B) UNION ALL (B EXCEPT ALL A)` does inside the database,
so that the SQLite/MongoDB/Redis fallback grades identically to PostgreSQL and MariaDB.

Column names are deliberately ignored. Set operations in SQL match columns by position,
so `SELECT name AS full_name` and `SELECT name` are the same answer.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Sequence

from .normalize import describe_row, normalize_rows

KIND_OK = 'ok'
KIND_COLUMN_COUNT = 'column_count'
KIND_ROWS = 'rows'
KIND_ORDER = 'order'
KIND_TRUNCATED = 'truncated'


@dataclass
class Diff:
    equal: bool
    kind: str = KIND_OK
    missing: list[tuple] = field(default_factory=list)
    extra: list[tuple] = field(default_factory=list)
    overlap: float = 0.0
    student_rows: int = 0
    expected_rows: int = 0
    student_columns: int = 0
    expected_columns: int = 0

    def describe_missing(self, limit: int = 3) -> str:
        return _preview(self.missing, limit)

    def describe_extra(self, limit: int = 3) -> str:
        return _preview(self.extra, limit)


def compare(
    student_columns: Sequence[str],
    student_rows: Sequence[Sequence[Any]],
    expected_columns: Sequence[str],
    expected_rows: Sequence[Sequence[Any]],
    *,
    ordered: bool = False,
    student_truncated: bool = False,
    expected_truncated: bool = False,
    lenient_numbers: bool = False,
) -> Diff:
    """Compare two result sets as multisets, optionally as ordered sequences."""
    if len(student_columns) != len(expected_columns):
        return Diff(
            equal=False,
            kind=KIND_COLUMN_COUNT,
            student_columns=len(student_columns),
            expected_columns=len(expected_columns),
            student_rows=len(student_rows),
            expected_rows=len(expected_rows),
        )

    if student_truncated or expected_truncated:
        # A truncated result is an arbitrary subset, so neither equality nor
        # inequality of the visible part says anything about the full result.
        return Diff(
            equal=False,
            kind=KIND_TRUNCATED,
            student_rows=len(student_rows),
            expected_rows=len(expected_rows),
            student_columns=len(student_columns),
            expected_columns=len(expected_columns),
        )

    student = normalize_rows(student_rows, lenient_numbers=lenient_numbers)
    expected = normalize_rows(expected_rows, lenient_numbers=lenient_numbers)

    student_counts = Counter(student)
    expected_counts = Counter(expected)

    missing = sorted((expected_counts - student_counts).elements(), key=_sort_key)
    extra = sorted((student_counts - expected_counts).elements(), key=_sort_key)

    matched = sum((student_counts & expected_counts).values())
    # Jaccard over multisets: a superset answer (dumping the whole table) must not
    # look almost right just because it contains every expected row.
    union = len(student) + len(expected) - matched
    overlap = matched / union if union else 1.0

    counts = (len(student), len(expected), len(student_columns), len(expected_columns))

    if missing or extra:
        return _diff(False, KIND_ROWS, counts, overlap, missing, extra)
    if ordered and student != expected:
        return _diff(False, KIND_ORDER, counts, 1.0)
    return _diff(True, KIND_OK, counts, 1.0)


def _diff(equal, kind, counts, overlap, missing=None, extra=None) -> Diff:
    s_rows, e_rows, s_cols, e_cols = counts
    return Diff(
        equal=equal,
        kind=kind,
        missing=missing or [],
        extra=extra or [],
        overlap=overlap,
        student_rows=s_rows,
        expected_rows=e_rows,
        student_columns=s_cols,
        expected_columns=e_cols,
    )


def _sort_key(row: tuple) -> str:
    return describe_row(row)


def _preview(rows: Sequence[tuple], limit: int) -> str:
    if not rows:
        return ''
    shown = '; '.join(describe_row(r) for r in rows[:limit])
    rest = len(rows) - limit
    return f'{shown} (ще {rest})' if rest > 0 else shown
