"""Sandbox app configuration."""

import os
import logging
from django.apps import AppConfig

logger = logging.getLogger(__name__)


class SandboxConfig(AppConfig):
    """Configuration for the sandbox app."""
    name = 'sandbox'
    default_auto_field = 'django.db.models.BigAutoField'

    def ready(self):
        """Called when Django is ready."""
        # Only start pool in the main process, not in migrations or tests
        if os.environ.get('RUN_MAIN') == 'true' or os.environ.get('WARM_POOL_START') == 'true':
            self._start_warm_pool()

    def _start_warm_pool(self):
        """Start the warm pool in background."""
        try:
            from .pool import start_warm_pool
            import threading

            # Start pool in background thread to not block startup
            thread = threading.Thread(
                target=start_warm_pool,
                name='warm-pool-startup',
                daemon=True,
            )
            thread.start()
            logger.info('Warm pool startup initiated')

        except Exception as e:
            logger.warning(f'Failed to start warm pool: {e}')
