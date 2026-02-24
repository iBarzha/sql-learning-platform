"""Management command to control the warm pool."""

import signal
import sys
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Start and manage the warm pool of database containers'

    def add_arguments(self, parser):
        parser.add_argument(
            'action',
            choices=['start', 'stop', 'status'],
            help='Action to perform'
        )
        parser.add_argument(
            '--foreground',
            '-f',
            action='store_true',
            help='Run in foreground (for start action)'
        )

    def handle(self, *args, **options):
        action = options['action']

        if action == 'start':
            self.start_pool(options['foreground'])
        elif action == 'stop':
            self.stop_pool()
        elif action == 'status':
            self.show_status()

    def start_pool(self, foreground: bool):
        """Start the warm pool."""
        from sandbox.pool import start_sandbox_pool, get_sandbox_pool

        self.stdout.write('Starting sandbox pool...')
        start_sandbox_pool()

        if foreground:
            self.stdout.write(self.style.SUCCESS('Sandbox pool started. Press Ctrl+C to stop.'))

            def signal_handler(sig, frame):
                self.stdout.write('\nStopping sandbox pool...')
                get_sandbox_pool().stop()
                sys.exit(0)

            signal.signal(signal.SIGINT, signal_handler)
            signal.signal(signal.SIGTERM, signal_handler)

            # Keep running
            import time
            while True:
                time.sleep(1)
        else:
            self.stdout.write(self.style.SUCCESS('Sandbox pool started in background.'))

    def stop_pool(self):
        """Stop the warm pool."""
        from sandbox.pool import stop_sandbox_pool

        self.stdout.write('Stopping sandbox pool...')
        stop_sandbox_pool()
        self.stdout.write(self.style.SUCCESS('Sandbox pool stopped.'))

    def show_status(self):
        """Show warm pool status."""
        from sandbox.pool import get_sandbox_pool

        pool = get_sandbox_pool()
        stats = pool.get_stats()

        self.stdout.write(f"\nSandbox Pool Status:")
        self.stdout.write(f"  Running: {stats['running']}")
        self.stdout.write(f"\nDatabase Pools:")

        for db_type, pool_stats in stats['pools'].items():
            available = pool_stats.get('available', 0)
            busy = pool_stats.get('busy', 0)
            self.stdout.write(
                f"  {db_type}: {available} available, {busy} busy"
            )

        sqlite_stats = stats.get('sqlite', {})
        self.stdout.write(
            f"  sqlite: {sqlite_stats.get('available', 1)} available (in-memory)"
        )
