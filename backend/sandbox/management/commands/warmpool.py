"""Management command to control the sandbox pool."""

import signal
import sys
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Start and manage the sandbox database pool'

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
        from sandbox.pool import get_warm_pool, start_warm_pool, stop_warm_pool

        action = options['action']

        if action == 'start':
            self.start_pool(options['foreground'])
        elif action == 'stop':
            self.stop_pool()
        elif action == 'status':
            self.show_status()

    def start_pool(self, foreground: bool):
        """Start the sandbox pool."""
        from sandbox.pool import start_warm_pool, get_warm_pool

        self.stdout.write('Starting sandbox pool...')
        start_warm_pool()

        if foreground:
            self.stdout.write(self.style.SUCCESS('Sandbox pool started. Press Ctrl+C to stop.'))

            def signal_handler(sig, frame):
                self.stdout.write('\nStopping sandbox pool...')
                get_warm_pool().stop()
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
        """Stop the sandbox pool."""
        from sandbox.pool import stop_warm_pool

        self.stdout.write('Stopping sandbox pool...')
        stop_warm_pool()
        self.stdout.write(self.style.SUCCESS('Sandbox pool stopped.'))

    def show_status(self):
        """Show sandbox pool status."""
        from sandbox.pool import get_warm_pool

        pool = get_warm_pool()
        stats = pool.get_stats()

        self.stdout.write(f"\nSandbox Pool Status:")
        self.stdout.write(f"  Running: {stats.get('running', False)}")

        self.stdout.write(f"\nDatabase Pools:")
        for db_type, pool_stats in stats.get('pools', {}).items():
            self.stdout.write(
                f"  {db_type}: {pool_stats.get('available', 0)} available, "
                f"{pool_stats.get('busy', 0)} busy"
            )

        sqlite_stats = stats.get('sqlite', {})
        if sqlite_stats:
            self.stdout.write(
                f"  sqlite: {sqlite_stats.get('available', 0)} available, "
                f"{sqlite_stats.get('busy', 0)} busy"
            )
