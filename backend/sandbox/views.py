"""API views for sandbox management."""

from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser

from .pool import get_warm_pool
from .services import get_query_service, ExecutionRequest


class PoolStatsView(APIView):
    """Get warm pool statistics."""
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request):
        """Return current pool statistics."""
        service = get_query_service()
        stats = service.get_stats()
        return Response(stats)


class PoolHealthView(APIView):
    """Health check endpoint for the warm pool."""
    permission_classes = []  # Public endpoint for load balancer

    def get(self, request):
        """Check if pool is healthy."""
        try:
            pool = get_warm_pool()
            stats = pool.get_stats()

            if not stats['running']:
                return Response(
                    {'status': 'unhealthy', 'reason': 'Pool not running'},
                    status=status.HTTP_503_SERVICE_UNAVAILABLE
                )

            # Check if at least one database type has available containers
            has_containers = any(
                p['available'] > 0 or p['busy'] < 10
                for p in stats['pools'].values()
            )

            if not has_containers:
                return Response(
                    {'status': 'degraded', 'reason': 'No containers available'},
                    status=status.HTTP_503_SERVICE_UNAVAILABLE
                )

            return Response({
                'status': 'healthy',
                'pools': stats['pools'],
            })

        except Exception as e:
            return Response(
                {'status': 'unhealthy', 'reason': str(e)},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )


class TestQueryView(APIView):
    """Test endpoint for executing queries (admin only)."""
    permission_classes = [IsAuthenticated, IsAdminUser]

    def post(self, request):
        """Execute a test query."""
        database_type = request.data.get('database_type', 'postgresql')
        query = request.data.get('query', '')
        schema_sql = request.data.get('schema_sql', '')
        seed_sql = request.data.get('seed_sql', '')

        if not query:
            return Response(
                {'error': 'Query is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        service = get_query_service()
        req = ExecutionRequest(
            database_type=database_type,
            query=query,
            schema_sql=schema_sql,
            seed_sql=seed_sql,
            user_id=request.user.id,
        )

        response = service.execute(req)

        return Response(response.to_dict())


class WarmPoolControlView(APIView):
    """Control the warm pool (admin only)."""
    permission_classes = [IsAuthenticated, IsAdminUser]

    def post(self, request):
        """Control warm pool operations."""
        action = request.data.get('action')
        pool = get_warm_pool()

        if action == 'start':
            pool.start()
            return Response({'status': 'started'})

        elif action == 'stop':
            pool.stop()
            return Response({'status': 'stopped'})

        elif action == 'warm':
            db_type = request.data.get('database_type')
            if db_type:
                pool._warm_pool(db_type)
                return Response({'status': f'warmed {db_type}'})
            else:
                return Response(
                    {'error': 'database_type required'},
                    status=status.HTTP_400_BAD_REQUEST
                )

        else:
            return Response(
                {'error': 'Invalid action. Use: start, stop, warm'},
                status=status.HTTP_400_BAD_REQUEST
            )
