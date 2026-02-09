"""Sandbox pool manager for database containers."""

import logging
import threading
import time
from dataclasses import dataclass
from typing import Optional

from django.conf import settings

from .executors import get_executor, BaseExecutor, QueryResult
from .exceptions import (
    NoAvailableContainerError,
    DatabaseConnectionError,
)
from .query_validator import (
    validate_sql,
    validate_mongodb,
    validate_redis,
    QueryBlockedError,
)

logger = logging.getLogger(__name__)


@dataclass
class DatabaseConfig:
    """Configuration for a sandbox database."""
    host: str
    port: int
    database: str = 'sandbox'
    user: str = 'sandbox'
    password: str = 'sandbox'


# Static sandbox container configurations (from docker-compose)
SANDBOX_DATABASES = {
    'postgresql': DatabaseConfig(
        host='sql-sandbox-postgres',
        port=5432,
        database='sandbox',
        user='sandbox',
        password='sandbox',
    ),
    # Restricted role for student query execution (defense-in-depth)
    'postgresql_student': DatabaseConfig(
        host='sql-sandbox-postgres',
        port=5432,
        database='sandbox',
        user='sandbox_student',
        password='sandbox_student',
    ),
    'mariadb': DatabaseConfig(
        host='sql-sandbox-mariadb',
        port=3306,
        database='sandbox',
        user='sandbox',
        password='sandbox',
    ),
    # Restricted user for student query execution
    'mariadb_student': DatabaseConfig(
        host='sql-sandbox-mariadb',
        port=3306,
        database='sandbox',
        user='sandbox_student',
        password='sandbox_student',
    ),
    'mongodb': DatabaseConfig(
        host='sql-sandbox-mongodb',
        port=27017,
        database='sandbox',
    ),
    'redis': DatabaseConfig(
        host='sql-sandbox-redis',
        port=6379,
    ),
}


class SandboxPool:
    """
    Manages connections to sandbox database containers.

    Uses static docker-compose containers instead of dynamic creation.
    Each query gets a fresh connection with isolated state.
    """

    def __init__(self):
        self._lock = threading.RLock()
        self._running = False
        self._available: dict[str, bool] = {}
        self._check_thread: Optional[threading.Thread] = None

    def start(self) -> None:
        """Start the pool and check database availability."""
        if self._running:
            return

        self._running = True
        logger.info('Starting sandbox pool...')

        # Initial availability check
        self._check_availability()

        # Start background health check
        self._check_thread = threading.Thread(
            target=self._health_check_loop,
            daemon=True,
            name='sandbox-pool-health',
        )
        self._check_thread.start()

        logger.info('Sandbox pool started')

    def stop(self) -> None:
        """Stop the pool."""
        self._running = False
        logger.info('Sandbox pool stopped')

    # Primary database types to health-check (excludes _student variants)
    _PRIMARY_DB_TYPES = ('postgresql', 'mariadb', 'mongodb', 'redis')

    def _check_availability(self) -> None:
        """Check which databases are available."""
        for db_type in self._PRIMARY_DB_TYPES:
            config = SANDBOX_DATABASES.get(db_type)
            if not config:
                continue
            try:
                executor_class = get_executor(db_type)
                executor = executor_class(
                    host=config.host,
                    port=config.port,
                    database=config.database,
                    user=config.user,
                    password=config.password,
                )
                executor.connect()
                executor.disconnect()
                self._available[db_type] = True
                logger.info(f'{db_type} sandbox is available')
            except Exception as e:
                self._available[db_type] = False
                logger.warning(f'{db_type} sandbox is not available: {e}')

    def _health_check_loop(self) -> None:
        """Background health check loop."""
        while self._running:
            time.sleep(60)  # Check every minute
            try:
                self._check_availability()
            except Exception as e:
                logger.error(f'Health check error: {e}')

    def is_available(self, database_type: str) -> bool:
        """Check if a database type is available."""
        # SQLite is always available (in-memory)
        if database_type == 'sqlite':
            return True
        return self._available.get(database_type, False)

    def get_executor(self, database_type: str) -> BaseExecutor:
        """Get an executor for the specified database type."""
        if database_type == 'sqlite':
            executor_class = get_executor(database_type)
            executor = executor_class()
            executor.connect()
            return executor

        if database_type not in SANDBOX_DATABASES:
            raise ValueError(f'Unknown database type: {database_type}')

        config = SANDBOX_DATABASES[database_type]
        executor_class = get_executor(database_type)
        executor = executor_class(
            host=config.host,
            port=config.port,
            database=config.database,
            user=config.user,
            password=config.password,
        )
        executor.connect()
        return executor

    def execute_query(
        self,
        database_type: str,
        query: str,
        schema_sql: str = '',
        seed_sql: str = '',
        timeout: int = 30,
    ) -> QueryResult:
        """Execute a query in the sandbox."""
        # ── Security: validate query before execution ───────
        try:
            if database_type in ('sqlite', 'postgresql', 'mariadb'):
                validate_sql(query)
            elif database_type == 'mongodb':
                validate_mongodb(query)
            elif database_type == 'redis':
                validate_redis(query)
        except QueryBlockedError as e:
            self._log_blocked_query(query, database_type, e.message)
            return QueryResult(
                success=False,
                error_message=e.message,
            )

        executor = None
        try:
            executor = self.get_executor(database_type)

            # Reset and initialize schema/data
            executor.reset()

            if schema_sql:
                result = executor.initialize_schema(schema_sql)
                if not result.success:
                    return result

            if seed_sql:
                result = executor.load_data(seed_sql)
                if not result.success:
                    return result

            # Execute the actual query
            return executor.execute_query(query, timeout=timeout)

        except Exception as e:
            logger.error(f'Query execution error: {e}')
            return QueryResult(
                success=False,
                error_message=str(e),
            )

        finally:
            if executor:
                try:
                    executor.disconnect()
                except Exception:
                    pass

    # ── Session-based execution ────────────────────────────────

    def execute_query_in_session(
        self,
        session_id: str,
        database_type: str,
        query: str,
        schema_sql: str = '',
        seed_sql: str = '',
        timeout: int = 30,
        user_id: Optional[int] = None,
    ) -> QueryResult:
        """Execute a query in a persistent session."""
        from .session_manager import get_session_manager

        # Security: validate query (same as stateless path)
        try:
            if database_type in ('sqlite', 'postgresql', 'mariadb'):
                validate_sql(query)
            elif database_type == 'mongodb':
                validate_mongodb(query)
            elif database_type == 'redis':
                validate_redis(query)
        except QueryBlockedError as e:
            self._log_blocked_query(
                query, database_type, e.message,
                user_id=user_id, session_id=session_id,
            )
            return QueryResult(
                success=False,
                error_message=e.message,
            )

        try:
            manager = get_session_manager()
            manager.get_or_create(
                session_id, database_type, schema_sql, seed_sql,
                user_id=user_id,
            )
            return manager.execute(
                session_id, query, timeout=timeout, user_id=user_id,
            )
        except Exception as e:
            logger.error(f'Session query error: {e}')
            return QueryResult(
                success=False,
                error_message=str(e),
            )

    def reset_session(self, session_id: str) -> None:
        """Reset (destroy) a session."""
        from .session_manager import get_session_manager
        manager = get_session_manager()
        manager.destroy(session_id)

    def destroy_session(self, session_id: str) -> None:
        """Destroy a session (alias for reset_session)."""
        self.reset_session(session_id)

    @staticmethod
    def _log_blocked_query(
        query: str,
        database_type: str,
        error_message: str,
        user_id: Optional[int] = None,
        session_id: str = '',
    ) -> None:
        """Log a blocked query to the audit log."""
        try:
            from .models import ExecutionLog
            ExecutionLog.objects.create(
                query=query[:4096],
                database_type=database_type,
                session_id=session_id or '',
                user_id=user_id,
                execution_time_ms=0,
                success=False,
                error_message=error_message,
                was_blocked=True,
            )
        except Exception as exc:
            logger.warning(f'Failed to log blocked query: {exc}')

    def get_stats(self) -> dict:
        """Get pool statistics."""
        return {
            'running': self._running,
            'pools': {
                db_type: {
                    'available': 1 if self._available.get(db_type, False) else 0,
                    'busy': 0,
                }
                for db_type in self._PRIMARY_DB_TYPES
            },
            'sqlite': {'available': 1, 'busy': 0},
        }


# Global pool instance
_sandbox_pool: Optional[SandboxPool] = None
_pool_lock = threading.Lock()


def get_sandbox_pool() -> SandboxPool:
    """Get the global sandbox pool instance."""
    global _sandbox_pool
    with _pool_lock:
        if _sandbox_pool is None:
            _sandbox_pool = SandboxPool()
        return _sandbox_pool


def get_warm_pool() -> SandboxPool:
    """Alias for get_sandbox_pool (backwards compatibility)."""
    return get_sandbox_pool()


def start_sandbox_pool() -> None:
    """Start the global sandbox pool."""
    pool = get_sandbox_pool()
    pool.start()


def stop_sandbox_pool() -> None:
    """Stop the global sandbox pool."""
    global _sandbox_pool
    with _pool_lock:
        if _sandbox_pool is not None:
            _sandbox_pool.stop()
            _sandbox_pool = None


# Backwards compatibility
start_warm_pool = start_sandbox_pool
stop_warm_pool = stop_sandbox_pool
