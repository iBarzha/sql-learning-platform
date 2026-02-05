"""Management command to control the warm pool."""

import signal
import sys
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Start and manage the warm pool of database containers'

    def add_arguments(self, parser):
        parser.add_argument(
            'action',
            choices=['start', 'stop', 'status', 'warm'],
            help='Action to perform'
        )
        parser.add_argument(
            '--database-type',
            '-d',
            help='Database type for warm action'
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
        elif action == 'warm':
            self.warm_database(options['database_type'])

    def start_pool(self, foreground: bool):
        """Start the warm pool."""
        from sandbox.pool import start_warm_pool, get_warm_pool

        self.stdout.write('Starting warm pool...')
        start_warm_pool()

        if foreground:
            self.stdout.write(self.style.SUCCESS('Warm pool started. Press Ctrl+C to stop.'))

            def signal_handler(sig, frame):
                self.stdout.write('\nStopping warm pool...')
                get_warm_pool().stop()
                sys.exit(0)

            signal.signal(signal.SIGINT, signal_handler)
            signal.signal(signal.SIGTERM, signal_handler)

            # Keep running
            import time
            while True:
                time.sleep(1)
        else:
            self.stdout.write(self.style.SUCCESS('Warm pool started in background.'))

    def stop_pool(self):
        """Stop the warm pool."""
        from sandbox.pool import stop_warm_pool

        self.stdout.write('Stopping warm pool...')
        stop_warm_pool()
        self.stdout.write(self.style.SUCCESS('Warm pool stopped.'))

    def show_status(self):
        """Show warm pool status."""
        from sandbox.pool import get_warm_pool

        pool = get_warm_pool()
        stats = pool.get_stats()

        self.stdout.write(f"\nWarm Pool Status:")
        self.stdout.write(f"  Running: {stats['running']}")
        self.stdout.write(f"  Total busy: {stats['total_busy']}")
        self.stdout.write(f"\nPool Configuration:")
        self.stdout.write(f"  Pool size: {stats['config']['pool_size']}")
        self.stdout.write(f"  Max age: {stats['config']['max_age']}s")
        self.stdout.write(f"  Max executions: {stats['config']['max_executions']}")
        self.stdout.write(f"\nDatabase Pools:")

        for db_type, pool_stats in stats['pools'].items():
            self.stdout.write(
                f"  {db_type}: {pool_stats['available']} available, "
                f"{pool_stats['busy']} busy"
            )

    def warm_database(self, database_type: str):
        """Pre-warm containers for a specific database."""
        from sandbox.pool import get_warm_pool

        if not database_type:
            self.stderr.write(self.style.ERROR('--database-type is required for warm action'))
            return

        pool = get_warm_pool()
        self.stdout.write(f'Warming {database_type} containers...')
        pool._warm_pool(database_type)
        self.stdout.write(self.style.SUCCESS(f'{database_type} containers warmed.'))
