"""Warm pool manager for sandbox containers."""

import logging
import threading
import time
from collections import defaultdict
from dataclasses import dataclass
from typing import Optional
from queue import Queue, Empty

from django.conf import settings

from .container import (
    ContainerManager,
    ContainerInfo,
    get_container_manager,
    CONTAINER_CONFIGS,
)
from .executors import get_executor, BaseExecutor
from .exceptions import (
    NoAvailableContainerError,
    ContainerError,
)

logger = logging.getLogger(__name__)


@dataclass
class PoolConfig:
    """Configuration for the warm pool."""
    pool_size: int = 3  # Containers per database type
    max_container_age: int = 3600  # 1 hour
    max_executions: int = 100  # Recycle after N executions
    health_check_interval: int = 30  # seconds
    acquire_timeout: int = 30  # seconds to wait for container


class WarmPool:
    """
    Manages a pool of pre-initialized database containers.

    The pool maintains a configurable number of ready-to-use containers
    for each database type, reducing cold start latency for query execution.
    """

    def __init__(self, config: Optional[PoolConfig] = None):
        self.config = config or PoolConfig(
            pool_size=settings.SANDBOX_CONFIG.get('POOL_SIZE', 3),
            acquire_timeout=settings.SANDBOX_CONFIG.get('CONTAINER_TIMEOUT', 30),
        )
        self._manager = get_container_manager()
        self._pools: dict[str, Queue[ContainerInfo]] = defaultdict(Queue)
        self._busy: dict[str, ContainerInfo] = {}
        self._lock = threading.RLock()
        self._running = False
        self._maintenance_thread: Optional[threading.Thread] = None

    def start(self) -> None:
        """Start the warm pool and initialize containers."""
        if self._running:
            return

        self._running = True
        logger.info('Starting warm pool...')

        # Start maintenance thread
        self._maintenance_thread = threading.Thread(
            target=self._maintenance_loop,
            daemon=True,
            name='warm-pool-maintenance',
        )
        self._maintenance_thread.start()

        # Pre-warm containers for each database type
        for db_type in CONTAINER_CONFIGS:
            self._warm_pool(db_type)

        logger.info('Warm pool started')

    def stop(self) -> None:
        """Stop the warm pool and cleanup containers."""
        self._running = False

        logger.info('Stopping warm pool...')

        # Stop all containers
        with self._lock:
            for db_type, pool in self._pools.items():
                while not pool.empty():
                    try:
                        info = pool.get_nowait()
                        self._manager.stop_container(info.container_id)
                    except Empty:
                        break

            for info in self._busy.values():
                self._manager.stop_container(info.container_id)

            self._pools.clear()
            self._busy.clear()

        logger.info('Warm pool stopped')

    def acquire(self, database_type: str, timeout: Optional[int] = None) -> ContainerInfo:
        """
        Acquire a container from the pool.

        Args:
            database_type: Type of database (postgresql, mysql, etc.)
            timeout: Maximum time to wait for a container

        Returns:
            ContainerInfo for the acquired container

        Raises:
            NoAvailableContainerError: If no container available within timeout
        """
        timeout = timeout or self.config.acquire_timeout
        start_time = time.time()

        while time.time() - start_time < timeout:
            with self._lock:
                pool = self._pools[database_type]

                # Try to get from pool
                try:
                    info = pool.get_nowait()

                    # Verify container is still running
                    if self._manager.is_running(info.container_id):
                        self._busy[info.id] = info
                        info.touch()
                        logger.debug(f'Acquired container {info.container_id[:12]} from pool')
                        return info
                    else:
                        logger.debug(f'Container {info.container_id[:12]} is dead, discarding')
                        continue
                except Empty:
                    pass

            # No container available, try to create one
            try:
                info = self._manager.create_container(database_type)
                with self._lock:
                    self._busy[info.id] = info
                logger.debug(f'Created new container {info.container_id[:12]}')
                return info
            except ContainerError as e:
                logger.warning(f'Failed to create container: {e}')
                time.sleep(1)

        raise NoAvailableContainerError(
            f'No {database_type} container available within {timeout}s'
        )

    def release(self, info: ContainerInfo, reset: bool = True) -> None:
        """
        Release a container back to the pool.

        Args:
            info: Container info to release
            reset: Whether to reset the database state
        """
        with self._lock:
            if info.id in self._busy:
                del self._busy[info.id]

        # Check if container should be recycled
        should_recycle = (
            info.executions_count >= self.config.max_executions or
            time.time() - info.created_at > self.config.max_container_age
        )

        if should_recycle:
            logger.debug(f'Recycling container {info.container_id[:12]}')
            self._manager.stop_container(info.container_id)
            self._warm_pool(info.database_type, count=1)
            return

        # Reset database state if needed
        if reset:
            try:
                executor_class = get_executor(info.database_type)
                executor = executor_class(host=info.host, port=info.port)
                executor.connect()
                executor.reset()
                executor.disconnect()
            except Exception as e:
                logger.warning(f'Failed to reset container {info.container_id[:12]}: {e}')
                self._manager.stop_container(info.container_id)
                self._warm_pool(info.database_type, count=1)
                return

        # Return to pool
        with self._lock:
            pool = self._pools[info.database_type]
            if pool.qsize() < self.config.pool_size:
                pool.put(info)
                logger.debug(f'Released container {info.container_id[:12]} to pool')
            else:
                # Pool is full, stop this container
                self._manager.stop_container(info.container_id)

    def get_executor(self, info: ContainerInfo) -> BaseExecutor:
        """Get an executor for a container."""
        executor_class = get_executor(info.database_type)
        executor = executor_class(host=info.host, port=info.port)
        executor.connect()
        return executor

    def _warm_pool(self, database_type: str, count: Optional[int] = None) -> None:
        """Pre-warm the pool with containers."""
        count = count or self.config.pool_size

        with self._lock:
            current_size = self._pools[database_type].qsize()
            needed = count - current_size

        if needed <= 0:
            return

        logger.info(f'Warming {needed} {database_type} containers')

        for _ in range(needed):
            try:
                info = self._manager.create_container(database_type)
                with self._lock:
                    self._pools[database_type].put(info)
            except ContainerError as e:
                logger.error(f'Failed to warm container: {e}')

    def _maintenance_loop(self) -> None:
        """Background maintenance loop."""
        while self._running:
            try:
                self._health_check()
                self._cleanup_old_containers()
            except Exception as e:
                logger.error(f'Maintenance error: {e}')

            time.sleep(self.config.health_check_interval)

    def _health_check(self) -> None:
        """Check health of pooled containers."""
        with self._lock:
            for db_type, pool in list(self._pools.items()):
                healthy = Queue()
                dead_count = 0

                while not pool.empty():
                    try:
                        info = pool.get_nowait()
                        if self._manager.is_running(info.container_id):
                            healthy.put(info)
                        else:
                            dead_count += 1
                    except Empty:
                        break

                self._pools[db_type] = healthy

                if dead_count > 0:
                    logger.info(f'Found {dead_count} dead {db_type} containers')

        # Replenish pools
        for db_type in CONTAINER_CONFIGS:
            self._warm_pool(db_type)

    def _cleanup_old_containers(self) -> None:
        """Cleanup orphaned containers."""
        self._manager.cleanup_old_containers(
            max_age_seconds=self.config.max_container_age * 2
        )

    def get_stats(self) -> dict:
        """Get pool statistics."""
        with self._lock:
            pool_stats = {}
            for db_type in CONTAINER_CONFIGS:
                pool_stats[db_type] = {
                    'available': self._pools[db_type].qsize(),
                    'busy': sum(1 for i in self._busy.values()
                               if i.database_type == db_type),
                }

            return {
                'running': self._running,
                'pools': pool_stats,
                'total_busy': len(self._busy),
                'config': {
                    'pool_size': self.config.pool_size,
                    'max_age': self.config.max_container_age,
                    'max_executions': self.config.max_executions,
                },
            }


# Global pool instance
_warm_pool: Optional[WarmPool] = None
_pool_lock = threading.Lock()


def get_warm_pool() -> WarmPool:
    """Get the global warm pool instance."""
    global _warm_pool
    with _pool_lock:
        if _warm_pool is None:
            _warm_pool = WarmPool()
        return _warm_pool


def start_warm_pool() -> None:
    """Start the global warm pool."""
    pool = get_warm_pool()
    pool.start()


def stop_warm_pool() -> None:
    """Stop the global warm pool."""
    global _warm_pool
    with _pool_lock:
        if _warm_pool is not None:
            _warm_pool.stop()
            _warm_pool = None
