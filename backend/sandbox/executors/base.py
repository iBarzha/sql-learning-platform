"""Base executor interface for database queries."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any
import time


MAX_RESULT_ROWS = 1000


@dataclass
class QueryResult:
    """Result of a query execution."""
    success: bool
    columns: list[str] = field(default_factory=list)
    rows: list[list[Any]] = field(default_factory=list)
    row_count: int = 0
    affected_rows: int = 0
    execution_time_ms: int = 0
    error_message: str = ''
    truncated: bool = False

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            'success': self.success,
            'columns': self.columns,
            'rows': self.rows,
            'row_count': self.row_count,
            'affected_rows': self.affected_rows,
            'execution_time_ms': self.execution_time_ms,
            'error_message': self.error_message,
            'truncated': self.truncated,
        }


class BaseExecutor(ABC):
    """Abstract base class for database executors."""

    def __init__(self, host: str, port: int, database: str = 'sandbox',
                 user: str = 'sandbox', password: str = 'sandbox'):
        self.host = host
        self.port = port
        self.database = database
        self.user = user
        self.password = password
        self._connection = None

    @abstractmethod
    def connect(self) -> None:
        """Establish connection to the database."""
        pass

    @abstractmethod
    def disconnect(self) -> None:
        """Close the database connection."""
        pass

    @abstractmethod
    def is_connected(self) -> bool:
        """Check if connection is active."""
        pass

    @abstractmethod
    def execute_query(self, query: str, timeout: int = 10) -> QueryResult:
        """Execute a query and return the result."""
        pass

    @abstractmethod
    def initialize_schema(self, schema_sql: str) -> QueryResult:
        """Initialize database schema."""
        pass

    @abstractmethod
    def load_data(self, seed_sql: str) -> QueryResult:
        """Load seed data into the database."""
        pass

    @abstractmethod
    def reset(self) -> None:
        """Reset the database to clean state."""
        pass

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()

    def _measure_time(self, func, *args, **kwargs) -> tuple[Any, int]:
        """Execute function and measure time in milliseconds."""
        start = time.perf_counter()
        result = func(*args, **kwargs)
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        return result, elapsed_ms
