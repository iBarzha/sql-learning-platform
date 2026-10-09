"""Sandbox pool manager for database containers."""

import logging
import threading
import time
import uuid
from contextlib import contextmanager
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


def _endpoint(name: str, default_host: str, default_port: int) -> tuple[str, int]:
    """Compose hostnames by default; SANDBOX_<NAME>_HOST/_PORT override them so the
    backend can run on the host against published ports (see docker-compose.dev-ports.yml)."""
    import os
    host = os.getenv(f'SANDBOX_{name}_HOST', default_host)
    port = int(os.getenv(f'SANDBOX_{name}_PORT', default_port))
    return host, port


_PG_HOST, _PG_PORT = _endpoint('POSTGRESQL', 'sql-sandbox-postgres', 5432)
_MARIA_HOST, _MARIA_PORT = _endpoint('MARIADB', 'sql-sandbox-mariadb', 3306)
_MONGO_HOST, _MONGO_PORT = _endpoint('MONGODB', 'sql-sandbox-mongodb', 27017)
_REDIS_HOST, _REDIS_PORT = _endpoint('REDIS', 'sql-sandbox-redis', 6379)

# Static sandbox container configurations (from docker-compose)
SANDBOX_DATABASES = {
    'postgresql': DatabaseConfig(
        host=_PG_HOST,
        port=_PG_PORT,
        database='sandbox',
        user='sandbox',
        password='sandbox',
    ),
    # Restricted role for student query execution (defense-in-depth)
    'postgresql_student': DatabaseConfig(
        host=_PG_HOST,
        port=_PG_PORT,
        database='sandbox',
        user='sandbox_student',
        password='sandbox_student',
    ),
    'mariadb': DatabaseConfig(
        host=_MARIA_HOST,
        port=_MARIA_PORT,
        database='sandbox',
        user='sandbox',
        password='sandbox',
    ),
    # Restricted user for student query execution
    'mariadb_student': DatabaseConfig(
        host=_MARIA_HOST,
        port=_MARIA_PORT,
        database='sandbox',
        user='sandbox_student',
        password='sandbox_student',
    ),
    'mongodb': DatabaseConfig(
        host=_MONGO_HOST,
        port=_MONGO_PORT,
        database='sandbox',
    ),
    'redis': DatabaseConfig(
        host=_REDIS_HOST,
        port=_REDIS_PORT,
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
                validate_sql(query, database_type)
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

        try:
            with self._isolated(database_type, schema_sql, seed_sql) as executor:
                return executor.execute_query(query, timeout=timeout)
        except DatabaseConnectionError as e:
            return QueryResult(success=False, error_message=str(e))
        except Exception as e:
            logger.error(f'Query execution error: {e}')
            return QueryResult(
                success=False,
                error_message=str(e),
            )

    @contextmanager
    def _isolated(self, database_type: str, schema_sql: str, seed_sql: str):
        """A freshly seeded, private namespace for one execution.

        Grading runs many executions at once (every student, the reference, the
        hidden datasets). Sharing one database and dropping its tables before each
        run made those executions destroy each other's data under load, so each
        run gets its own PostgreSQL schema / MariaDB database / MongoDB database /
        Redis key prefix - the same mechanism the persistent sessions use - and
        drops it afterwards.
        """
        from .session_manager import get_session_manager

        manager = get_session_manager()
        isolation_id = f'g_{uuid.uuid4().hex[:16]}'
        executor = None
        try:
            if database_type == 'sqlite':
                executor = manager._create_sqlite_session(schema_sql, seed_sql)
            elif database_type == 'postgresql':
                executor = manager._create_postgresql_session(isolation_id, schema_sql, seed_sql)
            elif database_type == 'mariadb':
                executor = manager._create_mariadb_session(isolation_id, schema_sql, seed_sql)
            elif database_type == 'mongodb':
                executor = manager._create_mongodb_session(isolation_id, schema_sql, seed_sql)
            elif database_type == 'redis':
                executor = manager._create_redis_session(isolation_id, schema_sql, seed_sql)
            else:
                raise ValueError(f'Unknown database type: {database_type}')
            yield executor
        finally:
            if executor is not None:
                self._discard(database_type, isolation_id, executor, manager)

    @staticmethod
    def _discard(database_type: str, isolation_id: str, executor, manager) -> None:
        try:
            if database_type == 'mongodb' and getattr(executor, '_client', None):
                executor._client.drop_database(isolation_id)
            elif database_type == 'redis':
                executor.reset()
            executor.disconnect()
            if database_type == 'postgresql':
                manager._drop_pg_schema(isolation_id)
            elif database_type == 'mariadb':
                manager._drop_mariadb_database(isolation_id)
        except Exception as e:
            logger.warning(f'Failed to discard sandbox namespace {isolation_id}: {e}')

    def execute_sequence(
        self,
        database_type: str,
        queries: list[str],
        schema_sql: str = '',
        seed_sql: str = '',
        timeout: int = 30,
    ) -> list[QueryResult]:
        """Run several statements on one freshly seeded sandbox, in order.

        Stops at the first failure. Used by grading to inspect table state after a
        student's INSERT/UPDATE/DELETE: the statement and the follow-up SELECTs must
        see the same connection.
        """
        for query in queries:
            try:
                if database_type in ('sqlite', 'postgresql', 'mariadb'):
                    validate_sql(query, database_type)
                elif database_type == 'mongodb':
                    validate_mongodb(query)
                elif database_type == 'redis':
                    validate_redis(query)
            except QueryBlockedError as e:
                self._log_blocked_query(query, database_type, e.message)
                return [QueryResult(success=False, error_message=e.message)]

        try:
            with self._isolated(database_type, schema_sql, seed_sql) as executor:
                results = []
                for query in queries:
                    result = executor.execute_query(query, timeout=timeout)
                    results.append(result)
                    if not result.success:
                        break
                return results
        except DatabaseConnectionError as e:
            return [QueryResult(success=False, error_message=str(e))]
        except Exception as e:
            logger.error(f'Sequence execution error: {e}')
            return [QueryResult(success=False, error_message=str(e))]

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
                validate_sql(query, database_type)
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
