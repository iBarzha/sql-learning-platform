"""Session-based sandbox manager.

Provides persistent sandbox sessions where state survives across queries.
Sessions auto-expire after 15 minutes of inactivity.
"""

import json
import logging
import threading
import time
import uuid
from dataclasses import dataclass
from typing import Optional

import redis as redis_lib

from .executors import get_executor, BaseExecutor, QueryResult
from .exceptions import DatabaseConnectionError

logger = logging.getLogger(__name__)

SESSION_TTL = 15 * 60  # 15 minutes
CLEANUP_INTERVAL = 60  # check every 60 seconds
MAX_SESSIONS = 100  # hard cap on concurrent sessions
SESSION_REDIS_HOST = 'sql-session-redis'
SESSION_REDIS_PORT = 6379


@dataclass
class SandboxSession:
    """A persistent sandbox session."""
    session_id: str
    database_type: str
    schema_sql: str
    seed_sql: str
    executor: BaseExecutor
    created_at: float
    last_used_at: float
    isolation_id: Optional[str] = None  # schema name / db name / redis key prefix
    user_id: Optional[int] = None  # owner user ID — prevents session hijacking
    # Per-session lock so queries on the same session are serialized,
    # but different sessions run in parallel.
    _exec_lock: threading.Lock = None

    def __post_init__(self):
        if self._exec_lock is None:
            self._exec_lock = threading.Lock()


class SessionManager:
    """Manages persistent sandbox sessions with per-DB isolation.

    Locking strategy:
      - self._lock protects self._sessions dict (quick ops only)
      - Heavy I/O (DB connect, schema create, DROP) runs OUTSIDE self._lock
      - Each session has its own _exec_lock for query serialization
    """

    def __init__(self):
        self._sessions: dict[str, SandboxSession] = {}
        self._lock = threading.RLock()
        self._cleanup_thread: Optional[threading.Thread] = None
        self._running = False
        self._session_redis: Optional[redis_lib.Redis] = None

    def start(self) -> None:
        """Start the session manager and cleanup thread."""
        if self._running:
            return
        self._running = True
        self._connect_session_redis()
        self._cleanup_thread = threading.Thread(
            target=self._cleanup_loop,
            daemon=True,
            name='session-cleanup',
        )
        self._cleanup_thread.start()
        logger.info('Session manager started')

    def stop(self) -> None:
        """Stop the session manager and destroy all sessions."""
        self._running = False
        # Collect all sessions under lock, then destroy outside
        with self._lock:
            sessions_to_destroy = list(self._sessions.values())
            self._sessions.clear()
        for session in sessions_to_destroy:
            self._cleanup_session_resources(session)
        if self._session_redis:
            try:
                self._session_redis.close()
            except Exception:
                pass
            self._session_redis = None
        logger.info('Session manager stopped')

    def _connect_session_redis(self) -> None:
        """Connect to the dedicated session-redis for metadata storage."""
        try:
            self._session_redis = redis_lib.Redis(
                host=SESSION_REDIS_HOST,
                port=SESSION_REDIS_PORT,
                db=0,
                decode_responses=True,
                socket_timeout=5,
                socket_connect_timeout=5,
            )
            self._session_redis.ping()
            logger.info('Connected to session-redis for metadata')
        except Exception as e:
            logger.warning(f'Could not connect to session-redis: {e}. '
                           f'Cross-worker recovery disabled.')
            self._session_redis = None

    def get_or_create(
        self,
        session_id: str,
        database_type: str,
        schema_sql: str = '',
        seed_sql: str = '',
        user_id: Optional[int] = None,
    ) -> SandboxSession:
        """Get existing session or create a new one.

        Heavy I/O (session creation) runs OUTSIDE the global lock so
        20 users creating sessions concurrently won't serialize.
        """
        # Fast path: session exists
        with self._lock:
            session = self._sessions.get(session_id)
            if session and session.database_type == database_type:
                # Verify ownership — prevent session hijacking
                if session.user_id is not None:
                    if user_id is None or session.user_id != user_id:
                        raise DatabaseConnectionError(
                            'Session belongs to another user.'
                        )
                session.last_used_at = time.time()
                self._touch_redis_ttl(session_id)
                return session

            # DB type changed — mark old session for cleanup
            old_session = None
            if session:
                old_session = self._sessions.pop(session_id, None)

            # Check session limit
            if len(self._sessions) >= MAX_SESSIONS:
                raise DatabaseConnectionError(
                    f'Too many active sessions ({MAX_SESSIONS}). '
                    f'Please try again later.'
                )

        # Destroy old session OUTSIDE lock (heavy I/O)
        if old_session:
            self._cleanup_session_resources(old_session)
            self._delete_meta_from_redis(session_id)

        # Try cross-worker recovery OUTSIDE lock
        rebuilt = self._rebuild_from_redis(session_id, database_type)
        if rebuilt:
            with self._lock:
                # Double-check nobody else created it while we were rebuilding
                if session_id not in self._sessions:
                    self._sessions[session_id] = rebuilt
                    return rebuilt
                else:
                    # Someone else beat us, clean up our rebuild
                    self._cleanup_session_resources(rebuilt)
                    return self._sessions[session_id]

        # Create new session OUTSIDE lock (heavy I/O: connect + schema + seed)
        new_session = self._create_session(
            session_id, database_type, schema_sql, seed_sql,
        )

        # Stamp user_id on the new session
        new_session.user_id = user_id

        # Register session under lock (quick dict insert)
        with self._lock:
            if session_id in self._sessions:
                # Race: another thread created it. Clean up ours.
                self._cleanup_session_resources(new_session)
                return self._sessions[session_id]
            self._sessions[session_id] = new_session

        self._save_meta_to_redis(new_session)
        return new_session

    def execute(
        self, session_id: str, query: str, timeout: int = 30,
        user_id: Optional[int] = None,
    ) -> QueryResult:
        """Execute a query in an existing session."""
        # Grab session reference under global lock (fast)
        with self._lock:
            session = self._sessions.get(session_id)
            if not session:
                return QueryResult(
                    success=False,
                    error_message='SESSION_EXPIRED',
                )
            # Verify ownership
            if session.user_id is not None:
                if user_id is None or session.user_id != user_id:
                    return QueryResult(
                        success=False,
                        error_message='Session belongs to another user.',
                    )
            session.last_used_at = time.time()

        # Serialize queries on the SAME session (per-session lock),
        # but different sessions execute in parallel.
        with session._exec_lock:
            try:
                # Check connection is still alive
                if not session.executor.is_connected():
                    logger.warning(f'Session {session_id}: reconnecting stale connection')
                    try:
                        session.executor.connect()
                        # Restore PostgreSQL search_path after reconnect
                        if session.database_type == 'postgresql' and session.isolation_id:
                            from psycopg2 import sql as psql
                            with session.executor._connection.cursor() as cur:
                                cur.execute(psql.SQL('SET search_path TO {}').format(
                                    psql.Identifier(session.isolation_id)))
                    except Exception as e:
                        return QueryResult(
                            success=False,
                            error_message=f'Connection lost and reconnect failed: {e}',
                        )

                return session.executor.execute_query(query, timeout=timeout)
            except Exception as e:
                logger.error(f'Session {session_id} query error: {e}')
                return QueryResult(
                    success=False,
                    error_message=str(e),
                )

    def destroy(self, session_id: str) -> None:
        """Destroy a session and clean up its resources."""
        # Pop from dict under lock (fast)
        with self._lock:
            session = self._sessions.pop(session_id, None)
        # Cleanup outside lock (heavy I/O)
        if session:
            self._cleanup_session_resources(session)
            self._delete_meta_from_redis(session_id)
            logger.info(f'Destroyed session {session_id} ({session.database_type})')

    def _create_session(
        self,
        session_id: str,
        database_type: str,
        schema_sql: str,
        seed_sql: str,
    ) -> SandboxSession:
        """Create a new isolated session. Runs OUTSIDE the global lock."""
        now = time.time()
        isolation_id = f's_{uuid.uuid4().hex[:12]}'

        if database_type == 'sqlite':
            executor = self._create_sqlite_session(schema_sql, seed_sql)
        elif database_type == 'postgresql':
            executor = self._create_postgresql_session(
                isolation_id, schema_sql, seed_sql
            )
        elif database_type == 'mariadb':
            executor = self._create_mariadb_session(
                isolation_id, schema_sql, seed_sql
            )
        elif database_type == 'mongodb':
            executor = self._create_mongodb_session(
                isolation_id, schema_sql, seed_sql
            )
        elif database_type == 'redis':
            executor = self._create_redis_session(
                isolation_id, schema_sql, seed_sql
            )
        else:
            raise ValueError(f'Unsupported database type: {database_type}')

        return SandboxSession(
            session_id=session_id,
            database_type=database_type,
            schema_sql=schema_sql,
            seed_sql=seed_sql,
            executor=executor,
            created_at=now,
            last_used_at=now,
            isolation_id=isolation_id,
        )

    # ── Per-DB creation ──────────────────────────────────────────

    def _create_sqlite_session(
        self, schema_sql: str, seed_sql: str
    ) -> BaseExecutor:
        """Create an in-memory SQLite session."""
        executor_class = get_executor('sqlite')
        executor = executor_class()
        executor.connect()
        if schema_sql:
            result = executor.initialize_schema(schema_sql)
            if not result.success:
                executor.disconnect()
                raise DatabaseConnectionError(
                    f'Schema init failed: {result.error_message}'
                )
        if seed_sql:
            result = executor.load_data(seed_sql)
            if not result.success:
                executor.disconnect()
                raise DatabaseConnectionError(
                    f'Seed data failed: {result.error_message}'
                )
        return executor

    def _create_postgresql_session(
        self, isolation_id: str, schema_sql: str, seed_sql: str
    ) -> BaseExecutor:
        """Create a PostgreSQL session with its own schema."""
        from .pool import SANDBOX_DATABASES
        import psycopg2
        from psycopg2 import extensions

        config = SANDBOX_DATABASES['postgresql']

        student_config = SANDBOX_DATABASES.get('postgresql_student')

        # Admin connection to create schema + grant to sandbox_student
        admin_conn = psycopg2.connect(
            host=config.host,
            port=config.port,
            database=config.database,
            user=config.user,
            password=config.password,
            connect_timeout=10,
        )
        admin_conn.set_isolation_level(extensions.ISOLATION_LEVEL_AUTOCOMMIT)
        try:
            with admin_conn.cursor() as cur:
                from psycopg2 import sql as psql
                cur.execute(psql.SQL('CREATE SCHEMA IF NOT EXISTS {}').format(
                    psql.Identifier(isolation_id)))
                # Grant privileges to sandbox_student (defense-in-depth)
                if student_config:
                    cur.execute(psql.SQL('GRANT ALL ON SCHEMA {} TO sandbox_student').format(
                        psql.Identifier(isolation_id)))
                    cur.execute(psql.SQL('ALTER DEFAULT PRIVILEGES IN SCHEMA {} '
                        'GRANT ALL ON TABLES TO sandbox_student').format(
                        psql.Identifier(isolation_id)))
                    cur.execute(psql.SQL('ALTER DEFAULT PRIVILEGES IN SCHEMA {} '
                        'GRANT ALL ON SEQUENCES TO sandbox_student').format(
                        psql.Identifier(isolation_id)))
        finally:
            admin_conn.close()

        # Create executor — use restricted sandbox_student if available
        use_config = student_config or config
        executor_class = get_executor('postgresql')
        executor = executor_class(
            host=use_config.host,
            port=use_config.port,
            database=use_config.database,
            user=use_config.user,
            password=use_config.password,
        )
        executor.connect()

        # Set search_path to the isolated schema
        with executor._connection.cursor() as cur:
            from psycopg2 import sql as psql
            cur.execute(psql.SQL('SET search_path TO {}').format(
                psql.Identifier(isolation_id)))

        if schema_sql:
            result = executor.initialize_schema(schema_sql)
            if not result.success:
                executor.disconnect()
                self._drop_pg_schema(isolation_id)
                raise DatabaseConnectionError(
                    f'Schema init failed: {result.error_message}'
                )
        if seed_sql:
            result = executor.load_data(seed_sql)
            if not result.success:
                executor.disconnect()
                self._drop_pg_schema(isolation_id)
                raise DatabaseConnectionError(
                    f'Seed data failed: {result.error_message}'
                )
        return executor

    def _create_mariadb_session(
        self, isolation_id: str, schema_sql: str, seed_sql: str
    ) -> BaseExecutor:
        """Create a MariaDB session with its own database."""
        from .pool import SANDBOX_DATABASES
        import pymysql

        config = SANDBOX_DATABASES['mariadb']
        student_config = SANDBOX_DATABASES.get('mariadb_student')

        # Admin connection (root) to create database and grant access
        import os
        mariadb_root_pw = os.getenv('MARIADB_ROOT_PASSWORD', 'rootpassword')
        admin_conn = pymysql.connect(
            host=config.host,
            port=config.port,
            user='root',
            password=mariadb_root_pw,
            connect_timeout=10,
            autocommit=True,
        )
        try:
            with admin_conn.cursor() as cur:
                safe_id = isolation_id.replace('`', '``')
                cur.execute(f'CREATE DATABASE IF NOT EXISTS `{safe_id}`')
                # Grant to admin user (for schema setup)
                cur.execute(
                    f"GRANT ALL PRIVILEGES ON `{safe_id}`.* "
                    f"TO '{config.user}'@'%'"
                )
                # Grant to restricted student user (defense-in-depth)
                if student_config:
                    cur.execute(
                        f"GRANT ALL PRIVILEGES ON `{safe_id}`.* "
                        f"TO 'sandbox_student'@'%'"
                    )
                cur.execute('FLUSH PRIVILEGES')
        finally:
            admin_conn.close()

        # Use admin user for schema/seed setup first
        executor_class = get_executor('mariadb')
        admin_executor = executor_class(
            host=config.host,
            port=config.port,
            database=isolation_id,
            user=config.user,
            password=config.password,
        )
        admin_executor.connect()

        # Run schema and seed with admin privileges
        if schema_sql:
            result = admin_executor.initialize_schema(schema_sql)
            if not result.success:
                admin_executor.disconnect()
                self._drop_mariadb_database(isolation_id)
                raise DatabaseConnectionError(
                    f'Schema init failed: {result.error_message}'
                )
        if seed_sql:
            result = admin_executor.load_data(seed_sql)
            if not result.success:
                admin_executor.disconnect()
                self._drop_mariadb_database(isolation_id)
                raise DatabaseConnectionError(
                    f'Seed data failed: {result.error_message}'
                )
        admin_executor.disconnect()

        # Now create the actual executor with restricted student user
        use_config = student_config or config
        executor = executor_class(
            host=use_config.host,
            port=use_config.port,
            database=isolation_id,
            user=use_config.user,
            password=use_config.password,
        )
        executor.connect()
        return executor

    def _create_mongodb_session(
        self, isolation_id: str, schema_sql: str, seed_sql: str
    ) -> BaseExecutor:
        """Create a MongoDB session with its own database."""
        from .pool import SANDBOX_DATABASES

        config = SANDBOX_DATABASES['mongodb']
        executor_class = get_executor('mongodb')
        executor = executor_class(
            host=config.host,
            port=config.port,
            database=isolation_id,
        )
        executor.connect()

        if schema_sql:
            result = executor.initialize_schema(schema_sql)
            if not result.success:
                executor.disconnect()
                raise DatabaseConnectionError(
                    f'Schema init failed: {result.error_message}'
                )
        if seed_sql:
            result = executor.load_data(seed_sql)
            if not result.success:
                executor.disconnect()
                raise DatabaseConnectionError(
                    f'Seed data failed: {result.error_message}'
                )
        return executor

    def _create_redis_session(
        self, key_prefix: str, schema_sql: str, seed_sql: str
    ) -> BaseExecutor:
        """Create a Redis session isolated by key prefix."""
        from .pool import SANDBOX_DATABASES

        config = SANDBOX_DATABASES['redis']
        executor_class = get_executor('redis')
        executor = executor_class(
            host=config.host,
            port=config.port,
            key_prefix=key_prefix,
        )
        executor.connect()
        executor.reset()  # clean any leftover keys with this prefix

        if schema_sql:
            result = executor.initialize_schema(schema_sql)
            if not result.success:
                executor.disconnect()
                raise DatabaseConnectionError(
                    f'Schema init failed: {result.error_message}'
                )
        if seed_sql:
            result = executor.load_data(seed_sql)
            if not result.success:
                executor.disconnect()
                raise DatabaseConnectionError(
                    f'Seed data failed: {result.error_message}'
                )
        return executor

    # ── Session resource cleanup (runs OUTSIDE lock) ─────────────

    def _cleanup_session_resources(self, session: SandboxSession) -> None:
        """Clean up a session's DB resources. Safe to call outside lock."""
        db_type = session.database_type
        isolation_id = session.isolation_id

        try:
            if db_type == 'sqlite':
                session.executor.disconnect()
            elif db_type == 'postgresql':
                session.executor.disconnect()
                if isolation_id:
                    self._drop_pg_schema(isolation_id)
            elif db_type == 'mariadb':
                session.executor.disconnect()
                if isolation_id:
                    self._drop_mariadb_database(isolation_id)
            elif db_type == 'mongodb':
                if session.executor._client and isolation_id:
                    session.executor._client.drop_database(isolation_id)
                session.executor.disconnect()
            elif db_type == 'redis':
                session.executor.reset()  # prefix-scoped key cleanup
                session.executor.disconnect()
        except Exception as e:
            logger.warning(
                f'Error cleaning up session {session.session_id}: {e}'
            )

    def _drop_pg_schema(self, schema_name: str) -> None:
        """Drop a PostgreSQL schema."""
        from .pool import SANDBOX_DATABASES
        import psycopg2
        from psycopg2 import extensions

        config = SANDBOX_DATABASES['postgresql']
        try:
            conn = psycopg2.connect(
                host=config.host,
                port=config.port,
                database=config.database,
                user=config.user,
                password=config.password,
                connect_timeout=10,
            )
            conn.set_isolation_level(extensions.ISOLATION_LEVEL_AUTOCOMMIT)
            from psycopg2 import sql as psql
            with conn.cursor() as cur:
                cur.execute(psql.SQL('DROP SCHEMA IF EXISTS {} CASCADE').format(
                    psql.Identifier(schema_name)))
            conn.close()
        except Exception as e:
            logger.warning(f'Failed to drop PG schema {schema_name}: {e}')

    def _drop_mariadb_database(self, db_name: str) -> None:
        """Drop a MariaDB database."""
        from .pool import SANDBOX_DATABASES
        import pymysql

        config = SANDBOX_DATABASES['mariadb']
        try:
            import os
            mariadb_root_pw = os.getenv('MARIADB_ROOT_PASSWORD', 'rootpassword')
            conn = pymysql.connect(
                host=config.host,
                port=config.port,
                user='root',
                password=mariadb_root_pw,
                connect_timeout=10,
                autocommit=True,
            )
            with conn.cursor() as cur:
                safe_name = db_name.replace('`', '``')
                cur.execute(f'DROP DATABASE IF EXISTS `{safe_name}`')
            conn.close()
        except Exception as e:
            logger.warning(f'Failed to drop MariaDB database {db_name}: {e}')

    # ── Cross-worker recovery via session-redis ──────────────────

    def _save_meta_to_redis(self, session: SandboxSession) -> None:
        """Save session metadata to session-redis for cross-worker recovery."""
        if not self._session_redis:
            return
        try:
            meta = {
                'session_id': session.session_id,
                'database_type': session.database_type,
                'schema_sql': session.schema_sql,
                'seed_sql': session.seed_sql,
                'isolation_id': session.isolation_id or '',
                'created_at': session.created_at,
                'user_id': str(session.user_id) if session.user_id else None,
            }
            self._session_redis.setex(
                f'session:{session.session_id}',
                SESSION_TTL,
                json.dumps(meta),
            )
        except Exception as e:
            logger.warning(f'Failed to save session meta to redis: {e}')

    def _touch_redis_ttl(self, session_id: str) -> None:
        """Refresh the TTL of session metadata in Redis on activity."""
        if not self._session_redis:
            return
        try:
            self._session_redis.expire(f'session:{session_id}', SESSION_TTL)
        except Exception:
            pass

    def _delete_meta_from_redis(self, session_id: str) -> None:
        """Delete session metadata from session-redis."""
        if not self._session_redis:
            return
        try:
            self._session_redis.delete(f'session:{session_id}')
        except Exception:
            pass

    def _rebuild_from_redis(
        self, session_id: str, database_type: str
    ) -> Optional[SandboxSession]:
        """Try to rebuild a session from session-redis metadata (cross-worker)."""
        if not self._session_redis:
            return None
        try:
            raw = self._session_redis.get(f'session:{session_id}')
            if not raw:
                return None
            meta = json.loads(raw)
            if meta['database_type'] != database_type:
                return None

            # Rebuild by re-creating executor with stored schema/seed
            session = self._create_session(
                session_id,
                meta['database_type'],
                meta['schema_sql'],
                meta['seed_sql'],
            )

            # Restore user ownership from metadata
            session.user_id = meta.get('user_id')
            logger.info(f'Rebuilt session {session_id} from redis metadata')
            return session
        except Exception as e:
            logger.warning(f'Failed to rebuild session {session_id}: {e}')
            return None

    # ── Cleanup loop ─────────────────────────────────────────────

    def _cleanup_loop(self) -> None:
        """Background thread that kills sessions idle > 15 minutes."""
        while self._running:
            time.sleep(CLEANUP_INTERVAL)
            try:
                self._cleanup_expired()
            except Exception as e:
                logger.error(f'Session cleanup error: {e}')

    def _cleanup_expired(self) -> None:
        """Find and destroy expired sessions.

        Collects expired sessions under lock (fast), then cleans up outside.
        """
        now = time.time()
        expired_sessions: list[SandboxSession] = []

        with self._lock:
            expired_ids = [
                sid for sid, s in self._sessions.items()
                if now - s.last_used_at > SESSION_TTL
            ]
            for sid in expired_ids:
                session = self._sessions.pop(sid, None)
                if session:
                    expired_sessions.append(session)

        # Heavy cleanup outside lock
        for session in expired_sessions:
            logger.info(f'Expiring idle session {session.session_id}')
            self._cleanup_session_resources(session)
            self._delete_meta_from_redis(session.session_id)


# ── Global singleton ─────────────────────────────────────────────

_session_manager: Optional[SessionManager] = None
_manager_lock = threading.Lock()


def get_session_manager() -> SessionManager:
    """Get the global session manager instance."""
    global _session_manager
    with _manager_lock:
        if _session_manager is None:
            _session_manager = SessionManager()
        return _session_manager


def start_session_manager() -> None:
    """Start the global session manager."""
    manager = get_session_manager()
    manager.start()


def stop_session_manager() -> None:
    """Stop the global session manager."""
    global _session_manager
    with _manager_lock:
        if _session_manager is not None:
            _session_manager.stop()
            _session_manager = None
