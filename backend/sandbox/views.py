"""API views for sandbox management."""

from django.db.models import Q
from django.utils.decorators import method_decorator
from django_ratelimit.decorators import ratelimit

from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser

from .pool import get_sandbox_pool
from courses.models import Dataset


class ExecuteQueryView(APIView):
    """Execute query in sandbox - available for all authenticated users."""
    permission_classes = [IsAuthenticated]

    @method_decorator(ratelimit(key='user', rate='30/m', method='POST'))
    def post(self, request):
        """Execute a query in the sandbox."""
        database_type = request.data.get('database_type', 'sqlite')
        query = request.data.get('query', '')
        schema_sql = request.data.get('schema_sql', '')
        seed_sql = request.data.get('seed_sql', '')
        dataset_id = request.data.get('dataset_id')
        session_id = request.data.get('session_id')

        # Validate database type
        valid_types = ['sqlite', 'postgresql', 'mariadb', 'mongodb', 'redis']
        if database_type not in valid_types:
            return Response(
                {'error': f'Invalid database type. Must be one of: {", ".join(valid_types)}'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not query:
            return Response(
                {'error': 'Query is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # If dataset_id provided, load schema and seed from it
        if dataset_id:
            try:
                dataset = Dataset.objects.get(id=dataset_id)
                schema_sql = dataset.schema_sql
                seed_sql = dataset.seed_sql
            except Dataset.DoesNotExist:
                return Response(
                    {'error': 'Dataset not found'},
                    status=status.HTTP_404_NOT_FOUND
                )

        # Execute query using the sandbox pool
        pool = get_sandbox_pool()

        # Check availability for non-SQLite databases
        if database_type != 'sqlite' and not pool.is_available(database_type):
            return Response(
                {'error': f'{database_type} sandbox is not available. Please try again later.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )

        # Session-based execution
        if session_id:
            result = pool.execute_query_in_session(
                session_id=session_id,
                database_type=database_type,
                query=query,
                schema_sql=schema_sql,
                seed_sql=seed_sql,
                timeout=30,
                user_id=request.user.id,
            )
            response_data = result.to_dict()
            response_data['session_id'] = session_id
            return Response(response_data)

        # Stateless execution (backward compat)
        result = pool.execute_query(
            database_type=database_type,
            query=query,
            schema_sql=schema_sql,
            seed_sql=seed_sql,
            timeout=30,
        )

        return Response(result.to_dict())


class SessionResetView(APIView):
    """Reset/destroy a sandbox session."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        """Destroy a session so the next query starts fresh."""
        session_id = request.data.get('session_id')
        if not session_id:
            return Response(
                {'error': 'session_id is required'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Verify session ownership before allowing reset
        from .session_manager import get_session_manager
        manager = get_session_manager()
        session = manager._sessions.get(session_id)
        if session and session.user_id is not None and session.user_id != request.user.id:
            return Response(
                {'error': 'Not authorized to reset this session'},
                status=status.HTTP_403_FORBIDDEN,
            )

        pool = get_sandbox_pool()
        pool.reset_session(session_id)
        return Response({'status': 'reset'})


class DatabaseTypesView(APIView):
    """Get available database types."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """Return list of available database types with availability status."""
        pool = get_sandbox_pool()

        types = [
            {
                'value': 'sqlite',
                'label': 'SQLite',
                'description': 'Lightweight in-memory database. Great for learning SQL basics.',
                'available': True,
            },
            {
                'value': 'postgresql',
                'label': 'PostgreSQL',
                'description': 'Advanced open-source database with rich features.',
                'available': pool.is_available('postgresql'),
            },
            {
                'value': 'mariadb',
                'label': 'MariaDB',
                'description': 'MySQL-compatible database with additional features.',
                'available': pool.is_available('mariadb'),
            },
            {
                'value': 'mongodb',
                'label': 'MongoDB',
                'description': 'Document-oriented NoSQL database.',
                'available': pool.is_available('mongodb'),
            },
            {
                'value': 'redis',
                'label': 'Redis',
                'description': 'In-memory key-value store.',
                'available': pool.is_available('redis'),
            },
        ]
        return Response(types)


class PublicDatasetsView(APIView):
    """Get public datasets for sandbox practice."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """Return list of public datasets grouped by database type."""
        database_type = request.query_params.get('database_type')

        # Get standalone datasets (no course) + datasets from published courses
        queryset = Dataset.objects.filter(
            Q(course__isnull=True) | Q(course__is_published=True)
        ).select_related('course')

        if database_type:
            queryset = queryset.filter(database_type=database_type)

        datasets = []
        for dataset in queryset:
            datasets.append({
                'id': str(dataset.id),
                'name': dataset.name,
                'description': dataset.description,
                'course_title': dataset.course.title if dataset.course else None,
                'database_type': dataset.database_type,
                'schema_sql': dataset.schema_sql,
                'seed_sql': dataset.seed_sql,
            })

        return Response(datasets)


class PoolHealthView(APIView):
    """Health check endpoint for the sandbox pool."""
    permission_classes = []  # Public endpoint

    def get(self, request):
        """Check pool health and database availability."""
        pool = get_sandbox_pool()
        stats = pool.get_stats()

        if not stats['running']:
            return Response(
                {'status': 'unhealthy', 'reason': 'Pool not running'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )

        return Response({
            'status': 'healthy',
            'databases': stats['pools'],
        })


class PoolStatsView(APIView):
    """Get pool statistics (admin only)."""
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request):
        """Return pool statistics."""
        pool = get_sandbox_pool()
        return Response(pool.get_stats())
