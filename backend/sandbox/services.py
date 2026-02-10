"""High-level service for query execution."""

import logging
from dataclasses import dataclass
from datetime import timedelta
from typing import Optional
from uuid import UUID

from django.conf import settings
from django.utils import timezone

from .pool import get_sandbox_pool, SandboxPool
from .executors import QueryResult
from .models import ExecutionLog
from .exceptions import (
    SandboxError,
    QueryTimeoutError,
    DatasetInitializationError,
)

logger = logging.getLogger(__name__)


@dataclass
class ExecutionRequest:
    """Request to execute a query."""
    database_type: str
    query: str
    schema_sql: str = ''
    seed_sql: str = ''
    timeout: int = 10
    user_id: Optional[UUID] = None
    submission_id: Optional[UUID] = None
    dataset_id: Optional[UUID] = None


@dataclass
class ExecutionResponse:
    """Response from query execution."""
    success: bool
    result: Optional[QueryResult] = None
    error_message: str = ''
    execution_time_ms: int = 0
    container_id: str = ''

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        data = {
            'success': self.success,
            'error_message': self.error_message,
            'execution_time_ms': self.execution_time_ms,
        }
        if self.result:
            data.update(self.result.to_dict())
        return data


class QueryExecutionService:
    """
    Service for executing SQL queries in sandbox databases.

    Provides a high-level API for query execution with automatic
    database management, dataset initialization, and result handling.
    """

    def __init__(self, pool: Optional[SandboxPool] = None):
        self._pool = pool or get_sandbox_pool()
        self._max_query_time = settings.SANDBOX_CONFIG.get('MAX_QUERY_TIME', 30)

    def execute(self, request: ExecutionRequest) -> ExecutionResponse:
        """
        Execute a query in a sandbox database.

        Args:
            request: ExecutionRequest with query details

        Returns:
            ExecutionResponse with results or error
        """
        try:
            timeout = min(request.timeout, self._max_query_time)

            result = self._pool.execute_query(
                database_type=request.database_type,
                query=request.query,
                schema_sql=request.schema_sql,
                seed_sql=request.seed_sql,
                timeout=timeout,
            )

            # Log execution
            self._log_execution(
                database_type=request.database_type,
                query=request.query,
                result=result,
                user_id=request.user_id,
                submission_id=request.submission_id,
            )

            return ExecutionResponse(
                success=result.success,
                result=result,
                error_message=result.error_message,
                execution_time_ms=result.execution_time_ms,
                container_id=request.database_type,
            )

        except QueryTimeoutError as e:
            logger.warning(f'Query timeout: {e}')
            return ExecutionResponse(
                success=False,
                error_message=str(e),
            )

        except SandboxError as e:
            logger.error(f'Sandbox error: {e}')
            return ExecutionResponse(
                success=False,
                error_message=str(e),
            )

        except Exception as e:
            logger.exception(f'Unexpected error during query execution: {e}')
            return ExecutionResponse(
                success=False,
                error_message='Internal error during query execution',
            )

    def _log_execution(self, database_type: str, query: str, result: QueryResult,
                       user_id: Optional[UUID], submission_id: Optional[UUID]) -> None:
        """Log query execution to database."""
        try:
            ExecutionLog.objects.create(
                container=None,
                user_id=user_id,
                submission_id=submission_id,
                query=query[:10000],
                database_type=database_type,
                execution_time_ms=result.execution_time_ms,
                success=result.success,
                error_message=result.error_message[:1000] if result.error_message else '',
            )
        except Exception as e:
            logger.warning(f'Failed to log execution: {e}')

    def get_stats(self) -> dict:
        """Get service statistics."""
        pool_stats = self._pool.get_stats()

        try:
            recent_executions = ExecutionLog.objects.filter(
                created_at__gte=timezone.now() - timedelta(hours=1)
            ).count()

            success_count = ExecutionLog.objects.filter(
                created_at__gte=timezone.now() - timedelta(hours=1),
                success=True
            ).count()

            pool_stats['db_stats'] = {
                'executions_last_hour': recent_executions,
                'success_rate': success_count / recent_executions if recent_executions > 0 else 1.0,
            }
        except Exception as e:
            logger.warning(f'Failed to get DB stats: {e}')

        return pool_stats


# Global service instance
_query_service: Optional[QueryExecutionService] = None


def get_query_service() -> QueryExecutionService:
    """Get the global query execution service."""
    global _query_service
    if _query_service is None:
        _query_service = QueryExecutionService()
    return _query_service


def execute_query(
    database_type: str,
    query: str,
    schema_sql: str = '',
    seed_sql: str = '',
    timeout: int = 10,
    user_id: Optional[UUID] = None,
    submission_id: Optional[UUID] = None,
    dataset_id: Optional[UUID] = None,
) -> ExecutionResponse:
    """
    Execute a query in a sandbox database.

    Convenience function that uses the global service instance.
    """
    request = ExecutionRequest(
        database_type=database_type,
        query=query,
        schema_sql=schema_sql,
        seed_sql=seed_sql,
        timeout=timeout,
        user_id=user_id,
        submission_id=submission_id,
        dataset_id=dataset_id,
    )
    return get_query_service().execute(request)
