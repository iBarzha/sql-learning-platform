"""Sandbox app configuration."""

import os
import sys
import logging
from django.apps import AppConfig

logger = logging.getLogger(__name__)


class SandboxConfig(AppConfig):
    """Configuration for the sandbox app."""
    name = 'sandbox'
    default_auto_field = 'django.db.models.BigAutoField'

    def ready(self):
        """Called when Django is ready."""
        # Skip during migrations, tests, or management commands
        if any(cmd in sys.argv for cmd in ['migrate', 'makemigrations', 'test', 'collectstatic']):
            return

        # Start pool for runserver (RUN_MAIN) or gunicorn/production
        is_runserver = os.environ.get('RUN_MAIN') == 'true'
        is_gunicorn = 'gunicorn' in os.environ.get('SERVER_SOFTWARE', '')
        force_start = os.environ.get('SANDBOX_POOL_START') == 'true'

        if is_runserver or is_gunicorn or force_start:
            self._start_sandbox_pool()

    def _start_sandbox_pool(self):
        """Start the sandbox pool in background."""
        try:
            from .pool import start_sandbox_pool
            import threading

            # Start pool in background thread to not block startup
            thread = threading.Thread(
                target=start_sandbox_pool,
                name='sandbox-pool-startup',
                daemon=True,
            )
            thread.start()
            logger.info('Sandbox pool startup initiated')

        except Exception as e:
            logger.warning(f'Failed to start sandbox pool: {e}')
