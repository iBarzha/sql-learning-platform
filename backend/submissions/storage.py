"""Make engine results safe to store in a JSONField.

PostgreSQL and MariaDB return NUMERIC as Decimal and DATE/TIMESTAMP as date objects;
the standard JSON encoder rejects both, which used to turn a correct answer into HTTP 500.
"""

import datetime as dt
import math
from decimal import Decimal


def json_safe(value):
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        # jsonb has no NaN or Infinity; keep them readable as text.
        return value if math.isfinite(value) else str(value)
    if isinstance(value, Decimal):
        if not value.is_finite():
            return str(value)
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
