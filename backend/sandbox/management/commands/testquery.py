"""Management command to test query execution."""

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Test query execution in sandbox containers'

    def add_arguments(self, parser):
        parser.add_argument(
            'query',
            nargs='?',
            default='SELECT 1 as test',
            help='SQL query to execute'
        )
        parser.add_argument(
            '--database-type',
            '-d',
            default='postgresql',
            help='Database type (postgresql, mysql, mariadb, mongodb, redis)'
        )
        parser.add_argument(
            '--schema',
            '-s',
            help='Schema SQL to execute before query'
        )
        parser.add_argument(
            '--seed',
            help='Seed SQL to execute after schema'
        )

    def handle(self, *args, **options):
        from sandbox.services import execute_query

        query = options['query']
        db_type = options['database_type']
        schema_sql = options['schema'] or ''
        seed_sql = options['seed'] or ''

        self.stdout.write(f'Executing query on {db_type}...')
        self.stdout.write(f'Query: {query[:100]}{"..." if len(query) > 100 else ""}')

        if schema_sql:
            self.stdout.write(f'Schema: {schema_sql[:50]}...')
        if seed_sql:
            self.stdout.write(f'Seed: {seed_sql[:50]}...')

        self.stdout.write('')

        response = execute_query(
            database_type=db_type,
            query=query,
            schema_sql=schema_sql,
            seed_sql=seed_sql,
        )

        if response.success:
            self.stdout.write(self.style.SUCCESS('Query executed successfully!'))
            self.stdout.write(f'Execution time: {response.execution_time_ms}ms')

            if response.result:
                result = response.result
                if result.columns:
                    self.stdout.write(f'\nColumns: {", ".join(result.columns)}')
                    self.stdout.write(f'Rows: {result.row_count}')

                    if result.rows:
                        self.stdout.write('\nResults:')
                        # Print header
                        header = ' | '.join(str(c)[:20].ljust(20) for c in result.columns)
                        self.stdout.write(header)
                        self.stdout.write('-' * len(header))

                        # Print rows (max 10)
                        for row in result.rows[:10]:
                            row_str = ' | '.join(str(v)[:20].ljust(20) for v in row)
                            self.stdout.write(row_str)

                        if result.row_count > 10:
                            self.stdout.write(f'... and {result.row_count - 10} more rows')
        else:
            self.stdout.write(self.style.ERROR('Query failed!'))
            self.stdout.write(f'Error: {response.error_message}')
