"""Multiset comparison of query results.

Mirrors what `(A EXCEPT ALL B) UNION ALL (B EXCEPT ALL A)` does inside the database,
so that the SQLite/MongoDB/Redis fallback grades identically to PostgreSQL and MariaDB.

Column names are deliberately ignored. Set operations in SQL match columns by position,
so `SELECT name AS full_name` and `SELECT name` are the same answer.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Optional, Sequence

from .normalize import describe_row, loose_row, normalize_rows

KIND_OK = 'ok'
KIND_COLUMN_COUNT = 'column_count'
KIND_ROWS = 'rows'
KIND_ORDER = 'order'
KIND_TRUNCATED = 'truncated'

# Column permutations are searched by backtracking; beyond this width it is not worth it.
MAX_PERMUTED_COLUMNS = 10


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
    # The rows differ only in value types: '10' against 10, a date against its text.
    type_only: bool = False
    # column_permutation[i] is the student column that stands for expected column i;
    # set only when the columns had to be reordered to match.
    column_permutation: Optional[list[int]] = None

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
    key_positions: Optional[Sequence[int]] = None,
    ignore_column_order: bool = False,
) -> Diff:
    """Compare two result sets as multisets, optionally as ordered sequences.

    `key_positions` are the expected columns the reference sorts by: with them the
    order check compares only those keys, so rows that tie on every key may come
    back in any order. `ignore_column_order` accepts the right columns in another
    order, as long as one reordering makes every row match.
    """
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

    permutation = None
    if (missing or extra) and ignore_column_order:
        permutation = _column_permutation(student, expected, expected_counts)
        if permutation is not None:
            student = [tuple(row[j] for j in permutation) for row in student]
            missing, extra = [], []

    if missing or extra:
        # Computed on the student's own column order: a result that is both permuted
        # and type-mismatched gets the row list, not the hint.
        type_only = _differs_only_in_type(missing, extra)
        return _diff(False, KIND_ROWS, counts, overlap, missing, extra, type_only=type_only)
    if ordered and (_order_view(student, key_positions, len(expected_columns))
                    != _order_view(expected, key_positions, len(expected_columns))):
        return _diff(False, KIND_ORDER, counts, 1.0, column_permutation=permutation)
    return _diff(True, KIND_OK, counts, 1.0, column_permutation=permutation)


def _order_view(rows: list[tuple], key_positions: Optional[Sequence[int]], width: int) -> list:
    """What the order check compares: the sort keys when known, otherwise whole rows."""
    if not key_positions or not all(0 <= i < width for i in key_positions):
        return rows
    return [tuple(row[i] for i in key_positions) for row in rows]


def _differs_only_in_type(missing: list[tuple], extra: list[tuple]) -> bool:
    """The differing rows hold the same values, and some cells differ in type.

    Whitespace or '10' against '10.0' (both text) is a value difference, not a type one.
    """
    if Counter(map(loose_row, missing)) != Counter(map(loose_row, extra)):
        return False
    return Counter(map(_tags, missing)) != Counter(map(_tags, extra))


def _tags(row: tuple) -> tuple:
    return tuple(cell[0] if isinstance(cell, tuple) and cell else None for cell in row)


def _column_permutation(student: list[tuple], expected: list[tuple],
                        expected_counts: Counter) -> Optional[list[int]]:
    """A reordering of the student's columns that makes the multisets equal, or None.

    Candidates for an expected column are the student columns holding the same values.
    Two columns can hold the same values yet pair up differently within rows, so each
    partial assignment is checked against the rows projected onto the columns chosen so
    far; that prunes the search early, and at full width it verifies the whole rows.
    """
    width = len(expected[0]) if expected else 0
    if not width or width > MAX_PERMUTED_COLUMNS or len(student) != len(expected):
        return None
    student_values = [Counter(row[j] for row in student) for j in range(width)]
    candidates = []
    for i in range(width):
        values = Counter(row[i] for row in expected)
        candidates.append([j for j in range(width) if student_values[j] == values])
    expected_prefixes = [Counter(row[:i + 1] for row in expected) for i in range(width - 1)]
    expected_prefixes.append(expected_counts)

    chosen: list[int] = []

    def search(i: int) -> Optional[list[int]]:
        if i == width:
            return list(chosen)
        for j in candidates[i]:
            if j in chosen:
                continue
            chosen.append(j)
            projected = Counter(tuple(row[c] for c in chosen) for row in student)
            found = search(i + 1) if projected == expected_prefixes[i] else None
            chosen.pop()
            if found is not None:
                return found
        return None

    return search(0)


def _diff(equal, kind, counts, overlap, missing=None, extra=None, *, type_only=False,
          column_permutation=None) -> Diff:
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
        type_only=type_only,
        column_permutation=column_permutation,
    )


def _sort_key(row: tuple) -> str:
    return describe_row(row)


def _preview(rows: Sequence[tuple], limit: int) -> str:
    if not rows:
        return ''
    shown = '; '.join(describe_row(r) for r in rows[:limit])
    rest = len(rows) - limit
    return f'{shown} (ще {rest})' if rest > 0 else shown
