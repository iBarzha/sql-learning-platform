"""Docker container management for sandbox databases."""

import logging
import uuid
import time
from dataclasses import dataclass
from typing import Optional

import docker
from docker.errors import NotFound, APIError
from django.conf import settings

from .exceptions import (
    ContainerError,
    ContainerStartError,
    ContainerTimeoutError,
)

logger = logging.getLogger(__name__)


@dataclass
class ContainerConfig:
    """Configuration for a database container."""
    database_type: str
    image: str
    env: dict
    port: int
    healthcheck_query: str
    startup_timeout: int = 60
    memory_limit: str = '256m'
    cpu_period: int = 100000
    cpu_quota: int = 50000  # 50% of one CPU


# Database-specific configurations
CONTAINER_CONFIGS = {
    'postgresql': ContainerConfig(
        database_type='postgresql',
        image='postgres:15-alpine',
        env={
            'POSTGRES_DB': 'sandbox',
            'POSTGRES_USER': 'sandbox',
            'POSTGRES_PASSWORD': 'sandbox',
            'POSTGRES_HOST_AUTH_METHOD': 'md5',
        },
        port=5432,
        healthcheck_query='SELECT 1',
    ),
    'mysql': ContainerConfig(
        database_type='mysql',
        image='mysql:8.0',
        env={
            'MYSQL_DATABASE': 'sandbox',
            'MYSQL_USER': 'sandbox',
            'MYSQL_PASSWORD': 'sandbox',
            'MYSQL_ROOT_PASSWORD': 'rootpassword',
        },
        port=3306,
        healthcheck_query='SELECT 1',
        startup_timeout=90,  # MySQL takes longer to start
    ),
    'mariadb': ContainerConfig(
        database_type='mariadb',
        image='mariadb:10.11',
        env={
            'MARIADB_DATABASE': 'sandbox',
            'MARIADB_USER': 'sandbox',
            'MARIADB_PASSWORD': 'sandbox',
            'MARIADB_ROOT_PASSWORD': 'rootpassword',
        },
        port=3306,
        healthcheck_query='SELECT 1',
        startup_timeout=90,
    ),
    'mongodb': ContainerConfig(
        database_type='mongodb',
        image='mongo:7.0',
        env={
            'MONGO_INITDB_DATABASE': 'sandbox',
        },
        port=27017,
        healthcheck_query='db.runCommand({ping: 1})',
    ),
    'redis': ContainerConfig(
        database_type='redis',
        image='redis:7-alpine',
        env={},
        port=6379,
        healthcheck_query='PING',
        startup_timeout=30,
    ),
}


class ContainerInfo:
    """Information about a running container."""

    def __init__(self, container_id: str, database_type: str,
                 host: str, port: int, internal_port: int):
        self.id = str(uuid.uuid4())
        self.container_id = container_id
        self.database_type = database_type
        self.host = host
        self.port = port
        self.internal_port = internal_port
        self.created_at = time.time()
        self.last_used_at = time.time()
        self.executions_count = 0
        self.dataset_id: Optional[str] = None

    def touch(self):
        """Update last used timestamp."""
        self.last_used_at = time.time()
        self.executions_count += 1


class ContainerManager:
    """Manages Docker containers for database sandboxes."""

    def __init__(self):
        self._client: Optional[docker.DockerClient] = None
        self._network_name = settings.SANDBOX_CONFIG.get(
            'DOCKER_NETWORK', 'sql-learning-sandbox'
        )

    @property
    def client(self) -> docker.DockerClient:
        """Get or create Docker client."""
        if self._client is None:
            self._client = docker.from_env()
        return self._client

    def ensure_network(self) -> str:
        """Ensure sandbox network exists."""
        try:
            network = self.client.networks.get(self._network_name)
            return network.id
        except NotFound:
            logger.info(f'Creating network: {self._network_name}')
            network = self.client.networks.create(
                self._network_name,
                driver='bridge',
            )
            return network.id

    def pull_image(self, image: str) -> None:
        """Pull a Docker image if not present."""
        try:
            self.client.images.get(image)
            logger.debug(f'Image already present: {image}')
        except NotFound:
            logger.info(f'Pulling image: {image}')
            self.client.images.pull(image)

    def create_container(self, database_type: str) -> ContainerInfo:
        """Create a new database container."""
        config = CONTAINER_CONFIGS.get(database_type)
        if not config:
            raise ContainerError(f'Unsupported database type: {database_type}')

        # Use configured images from settings if available
        image = settings.SANDBOX_IMAGES.get(database_type, config.image)

        # Ensure image is available
        self.pull_image(image)

        # Ensure network exists
        self.ensure_network()

        container_name = f'sandbox-{database_type}-{uuid.uuid4().hex[:8]}'

        try:
            container = self.client.containers.run(
                image=image,
                name=container_name,
                environment=config.env,
                detach=True,
                remove=True,  # Auto-remove when stopped
                network=self._network_name,
                mem_limit=config.memory_limit,
                cpu_period=config.cpu_period,
                cpu_quota=config.cpu_quota,
                labels={
                    'sql-learning-sandbox': 'true',
                    'database-type': database_type,
                },
            )

            # Get container IP address
            container.reload()
            networks = container.attrs.get('NetworkSettings', {}).get('Networks', {})
            network_info = networks.get(self._network_name, {})
            ip_address = network_info.get('IPAddress', container_name)

            info = ContainerInfo(
                container_id=container.id,
                database_type=database_type,
                host=ip_address,
                port=config.port,
                internal_port=config.port,
            )

            # Wait for database to be ready
            self._wait_for_ready(info, config)

            logger.info(f'Container created: {container_name} ({info.host}:{info.port})')
            return info

        except APIError as e:
            raise ContainerStartError(f'Failed to create container: {e}')

    def _wait_for_ready(self, info: ContainerInfo, config: ContainerConfig) -> None:
        """Wait for database to be ready to accept connections."""
        from .executors import get_executor

        timeout = config.startup_timeout
        start_time = time.time()
        last_error = None

        executor_class = get_executor(info.database_type)

        while time.time() - start_time < timeout:
            try:
                executor = executor_class(
                    host=info.host,
                    port=info.port,
                )
                executor.connect()
                executor.disconnect()
                logger.debug(f'Container {info.container_id[:12]} is ready')
                return
            except Exception as e:
                last_error = e
                time.sleep(1)

        raise ContainerTimeoutError(
            f'Container failed to become ready within {timeout}s. Last error: {last_error}'
        )

    def stop_container(self, container_id: str) -> None:
        """Stop and remove a container."""
        try:
            container = self.client.containers.get(container_id)
            container.stop(timeout=5)
            logger.info(f'Container stopped: {container_id[:12]}')
        except NotFound:
            logger.debug(f'Container already removed: {container_id[:12]}')
        except APIError as e:
            logger.error(f'Error stopping container {container_id[:12]}: {e}')

    def is_running(self, container_id: str) -> bool:
        """Check if container is running."""
        try:
            container = self.client.containers.get(container_id)
            return container.status == 'running'
        except NotFound:
            return False

    def cleanup_old_containers(self, max_age_seconds: int = 3600) -> int:
        """Remove old sandbox containers."""
        count = 0
        try:
            containers = self.client.containers.list(
                all=True,
                filters={'label': 'sql-learning-sandbox=true'},
            )

            for container in containers:
                try:
                    created = container.attrs.get('Created', '')
                    # Docker timestamps are in ISO format
                    if created:
                        from datetime import datetime
                        created_time = datetime.fromisoformat(
                            created.replace('Z', '+00:00')
                        )
                        age = (datetime.now(created_time.tzinfo) - created_time).total_seconds()

                        if age > max_age_seconds:
                            container.stop(timeout=5)
                            count += 1
                            logger.info(f'Cleaned up old container: {container.id[:12]}')
                except Exception as e:
                    logger.warning(f'Error cleaning container {container.id[:12]}: {e}')

        except APIError as e:
            logger.error(f'Error during cleanup: {e}')

        return count

    def get_stats(self) -> dict:
        """Get statistics about sandbox containers."""
        try:
            containers = self.client.containers.list(
                filters={'label': 'sql-learning-sandbox=true'},
            )

            by_type = {}
            for container in containers:
                db_type = container.labels.get('database-type', 'unknown')
                by_type[db_type] = by_type.get(db_type, 0) + 1

            return {
                'total_containers': len(containers),
                'by_type': by_type,
            }
        except APIError:
            return {'total_containers': 0, 'by_type': {}}


# Global container manager instance
_container_manager: Optional[ContainerManager] = None


def get_container_manager() -> ContainerManager:
    """Get the global container manager instance."""
    global _container_manager
    if _container_manager is None:
        _container_manager = ContainerManager()
    return _container_manager
