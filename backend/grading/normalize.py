"""Canonicalization of query result values.

Pure Python on purpose: no Django imports, so it can be unit-tested without a database.

Values are returned as tagged tuples ('n', ...), ('s', ...) and so on. The tag keeps a
number from ever comparing equal to a string that merely looks like one, which is what
PostgreSQL does in a set operation - it refuses to match `text` against `integer`. The
Python fallback path has to agree with the in-database EXCEPT ALL path, otherwise the
same answer would be graded differently on SQLite and on PostgreSQL.
"""

from __future__ import annotations

import datetime as dt
import json
import re
import uuid
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP, localcontext
from typing import Any, Sequence

NUMERIC_PLACES = Decimal('1E-6')
_CALC_PRECISION = 60


class _Null:
    """NULL sentinel. Equal only to itself - never to '' or 0."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __repr__(self) -> str:
        return 'NULL'

    def __reduce__(self):
        return (_Null, ())


NULL = _Null()

TAG_NUMBER = 'n'
TAG_STRING = 's'
TAG_BYTES = 'b'
TAG_TEMPORAL = 't'
TAG_JSON = 'j'
TAG_NAN = 'nan'
TAG_INFINITY = 'inf'


_NUMERIC_TEXT = re.compile(r'^\s*[-+]?(\d+(\.\d*)?|\.\d+)([eE][-+]?\d+)?\s*$')


def normalize_value(value: Any, *, lenient_numbers: bool = False) -> Any:
    """Canonicalize one cell so that equal values compare equal across engines.

    `lenient_numbers` treats numeric-looking text as a number. Only legacy result
    snapshots need it: they were stored through DjangoJSONEncoder, which turns
    Decimal into a string.
    """
    if value is None:
        return NULL
    if lenient_numbers and isinstance(value, str) and _NUMERIC_TEXT.match(value):
        return _normalize_number(value.strip())

    # bool must be handled before int: bool subclasses int, and MariaDB returns 1/0
    # where PostgreSQL returns true/false for the same expression.
    if isinstance(value, bool):
        return (TAG_NUMBER, Decimal(1) if value else Decimal(0))

    if isinstance(value, (int, float, Decimal)):
        return _normalize_number(value)

    if isinstance(value, dt.datetime):
        return (TAG_TEMPORAL, _normalize_datetime(value))
    if isinstance(value, (dt.date, dt.time)):
        return (TAG_TEMPORAL, value.isoformat())
    if isinstance(value, dt.timedelta):
        return (TAG_NUMBER, _quantize(Decimal(str(value.total_seconds()))))

    if isinstance(value, (bytes, bytearray, memoryview)):
        return (TAG_BYTES, bytes(value).hex())

    if isinstance(value, uuid.UUID):
        return (TAG_STRING, str(value))

    if isinstance(value, (dict, list, tuple)):
        return (TAG_JSON, canonical_json(value))

    if isinstance(value, str):
        # rstrip only: CHAR(n) padding differs between engines, but leading
        # whitespace can be meaningful data.
        return (TAG_STRING, value.rstrip())

    return (TAG_STRING, str(value))


def _normalize_number(value: int | float | Decimal | str) -> tuple:
    try:
        d = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return (TAG_STRING, str(value))

    if d.is_nan():
        # NaN != NaN would break Counter-based comparison, so collapse it to one token.
        return (TAG_NAN,)
    if d.is_infinite():
        return (TAG_INFINITY, d > 0)
    return (TAG_NUMBER, _quantize(d))


def _quantize(d: Decimal) -> Decimal:
    with localcontext() as ctx:
        ctx.prec = _CALC_PRECISION
        try:
            value = d.quantize(NUMERIC_PLACES, rounding=ROUND_HALF_UP)
        except InvalidOperation:
            # Too large to quantize at this scale; it is already integral.
            value = d
        value = value.normalize()
        # normalize() turns Decimal('10.000000') into Decimal('1E+1'), which is
        # numerically fine but unreadable in feedback. Re-expand integral values.
        if value == value.to_integral_value():
            value = value.quantize(Decimal(1))
        return value


def _normalize_datetime(value: dt.datetime) -> str:
    if value.tzinfo is not None:
        value = value.astimezone(dt.timezone.utc).replace(tzinfo=None)
    return value.isoformat()


def canonical_json(value: Any, *, drop_keys: Sequence[str] = ()) -> str:
    """Stable JSON text for document results.

    MongoDB rows arrive as serialized documents. Without sorted keys two identical
    documents can differ only by insertion order, and `_id` is regenerated on every
    reseed, so it can never match a reference captured earlier.
    """
    return json.dumps(
        _strip_keys(value, set(drop_keys)),
        sort_keys=True,
        ensure_ascii=False,
        default=str,
        separators=(',', ':'),
    )


def _strip_keys(value: Any, drop: set) -> Any:
    if isinstance(value, dict):
        return {k: _strip_keys(v, drop) for k, v in value.items() if k not in drop}
    if isinstance(value, (list, tuple)):
        return [_strip_keys(v, drop) for v in value]
    return value


def normalize_row(row: Sequence[Any], *, lenient_numbers: bool = False) -> tuple:
    return tuple(normalize_value(cell, lenient_numbers=lenient_numbers) for cell in row)


def normalize_rows(rows: Sequence[Sequence[Any]], *, lenient_numbers: bool = False) -> list[tuple]:
    return [normalize_row(row, lenient_numbers=lenient_numbers) for row in rows]


def loose_value(value: Any) -> Any:
    """Tag-free form of a normalized value, for telling a type mismatch from a wrong value.

    A number and the numeric-looking text of it give the same text ('10', 10 and
    '10.0' all become '10'), as do a date and its ISO text. NULL, bytes, JSON, NaN and
    infinity are returned unchanged.
    """
    if not isinstance(value, tuple) or len(value) != 2:
        return value
    tag, payload = value
    if tag == TAG_NUMBER:
        return str(payload)
    if tag == TAG_STRING:
        if _NUMERIC_TEXT.match(payload):
            number = _normalize_number(payload.strip())
            if number[0] == TAG_NUMBER:
                return str(number[1])
        return payload.strip()
    if tag == TAG_TEMPORAL:
        return payload
    return value


def loose_row(row: Sequence[Any]) -> tuple:
    return tuple(loose_value(cell) for cell in row)


def describe_value(value: Any) -> str:
    """Human-readable form of a normalized value, for feedback messages."""
    if value is NULL:
        return 'NULL'
    if isinstance(value, tuple) and value:
        tag = value[0]
        if tag == TAG_NAN:
            return 'NaN'
        if tag == TAG_INFINITY:
            return 'Infinity' if value[1] else '-Infinity'
        return str(value[1])
    return str(value)


def describe_row(row: Sequence[Any]) -> str:
    return '(' + ', '.join(describe_value(c) for c in row) + ')'
