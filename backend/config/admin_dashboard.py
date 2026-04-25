"""Admin dashboard view aggregating server, DB, sandbox, and app metrics."""

import logging
import shutil
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db import connection
from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .permissions import IsAdmin

logger = logging.getLogger(__name__)


def _get_server_metrics():
    """CPU / RAM / disk usage. Falls back to None if psutil isn't available."""
    try:
        import psutil
    except ImportError:
        return None
    try:
        cpu = psutil.cpu_percent(interval=0.3)
        mem = psutil.virtual_memory()
        disk = shutil.disk_usage('/')
        boot_time = psutil.boot_time()
        uptime_seconds = int(timezone.now().timestamp() - boot_time)
        return {
            'cpu_percent': round(cpu, 1),
            'cpu_count': psutil.cpu_count(),
            'memory_total_mb': round(mem.total / 1024 / 1024),
            'memory_used_mb': round(mem.used / 1024 / 1024),
            'memory_percent': round(mem.percent, 1),
            'disk_total_gb': round(disk.total / 1024 / 1024 / 1024, 1),
            'disk_used_gb': round(disk.used / 1024 / 1024 / 1024, 1),
            'disk_percent': round(disk.used / disk.total * 100, 1),
            'uptime_seconds': uptime_seconds,
        }
    except Exception as e:
        logger.warning('server metrics failed: %s', e)
        return None


def _get_database_metrics():
    """PostgreSQL connection details and size info."""
    info = {
        'engine': connection.settings_dict.get('ENGINE', '').rsplit('.', 1)[-1],
        'name': connection.settings_dict.get('NAME'),
        'host': connection.settings_dict.get('HOST'),
        'port': connection.settings_dict.get('PORT'),
        'connected': False,
        'size_pretty': None,
        'tables': [],
    }
    try:
        with connection.cursor() as cur:
            cur.execute('SELECT 1')
            info['connected'] = cur.fetchone()[0] == 1
            # DB size
            cur.execute(
                "SELECT pg_size_pretty(pg_database_size(current_database())) AS size"
            )
            info['size_pretty'] = cur.fetchone()[0]
            # Table row counts (top 12 by size)
            cur.execute(
                """
                SELECT relname AS table, n_live_tup AS rows,
                       pg_size_pretty(pg_total_relation_size(relid)) AS size
                FROM pg_stat_user_tables
                ORDER BY n_live_tup DESC
                LIMIT 12
                """
            )
            info['tables'] = [
                {'name': r[0], 'rows': r[1], 'size': r[2]} for r in cur.fetchall()
            ]
    except Exception as e:
        logger.warning('db metrics failed: %s', e)
        info['error'] = str(e)
    return info


def _get_sandbox_metrics():
    """Sandbox container availability."""
    try:
        from sandbox.pool import get_sandbox_pool
        pool = get_sandbox_pool()
        return pool.get_stats()
    except Exception as e:
        logger.warning('sandbox metrics failed: %s', e)
        return {'error': str(e)}


def _get_app_stats():
    """Counts of users, courses, lessons, exercises, datasets, submissions."""
    from courses.models import Course, Dataset, Lesson, LessonExercise, Module
    from submissions.models import Submission

    User = get_user_model()
    now = timezone.now()
    last_24h = now - timedelta(hours=24)
    last_7d = now - timedelta(days=7)

    return {
        'users': {
            'total': User.objects.count(),
            'admins': User.objects.filter(role='admin').count(),
            'instructors': User.objects.filter(role='instructor').count(),
            'students': User.objects.filter(role='student').count(),
            'active_24h': User.objects.filter(last_login__gte=last_24h).count(),
        },
        'courses': {
            'total': Course.objects.count(),
            'published': Course.objects.filter(is_published=True).count(),
            'draft': Course.objects.filter(is_published=False).count(),
        },
        'modules': {'total': Module.objects.count()},
        'lessons': {
            'total': Lesson.objects.count(),
            'published': Lesson.objects.filter(is_published=True).count(),
        },
        'exercises': {'total': LessonExercise.objects.count()},
        'datasets': {
            'total': Dataset.objects.count(),
            'system': Dataset.objects.filter(created_by__isnull=True, course__isnull=True).count(),
            'instructor_owned': Dataset.objects.filter(created_by__isnull=False).count(),
        },
        'submissions': {
            'total': Submission.objects.count(),
            'last_24h': Submission.objects.filter(submitted_at__gte=last_24h).count(),
            'last_7d': Submission.objects.filter(submitted_at__gte=last_7d).count(),
            'correct': Submission.objects.filter(is_correct=True).count(),
        },
    }


def _get_recent_activity():
    """Recent users, recent submissions for quick overview."""
    from submissions.models import Submission

    User = get_user_model()
    recent_users = list(
        User.objects.order_by('-created_at')[:5].values(
            'id', 'email', 'full_name', 'role', 'created_at', 'last_login'
        )
    )
    recent_submissions = []
    for s in (
        Submission.objects.select_related('student', 'lesson', 'exercise', 'assignment')
        .order_by('-submitted_at')[:5]
    ):
        recent_submissions.append({
            'id': str(s.id),
            'student_email': s.student.email if s.student else None,
            'target': (
                s.lesson.title if s.lesson else (s.assignment.title if s.assignment else None)
            ),
            'exercise': s.exercise.title if s.exercise else None,
            'is_correct': s.is_correct,
            'score': float(s.score) if s.score is not None else None,
            'status': s.status,
            'submitted_at': s.submitted_at,
        })
    return {
        'recent_users': [
            {**u, 'id': str(u['id'])} for u in recent_users
        ],
        'recent_submissions': recent_submissions,
    }


class AdminDashboardView(APIView):
    """Aggregated metrics for the admin settings page."""

    permission_classes = [IsAuthenticated, IsAdmin]

    def get(self, request):
        return Response({
            'server': _get_server_metrics(),
            'database': _get_database_metrics(),
            'sandbox': _get_sandbox_metrics(),
            'stats': _get_app_stats(),
            'activity': _get_recent_activity(),
            'generated_at': timezone.now().isoformat(),
        })
