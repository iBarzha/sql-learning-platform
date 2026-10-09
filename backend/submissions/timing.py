"""Server-side lesson timer.

The countdown a student sees is only a display; what counts is the moment recorded
here when they first open the practice, and the deadline derived from it.
"""

from datetime import timedelta

from django.utils import timezone

from .models import UserResult

# Network latency and the last second of the countdown should not cost an answer.
GRACE_SECONDS = 10


def start_lesson(student, lesson) -> UserResult:
    """Record the first opening of a lesson's practice; later calls return the same row."""
    result, _ = UserResult.objects.get_or_create(
        student=student,
        lesson=lesson,
        exercise=None,
        assignment=None,
        defaults={'started_at': timezone.now()},
    )
    if result.started_at is None:
        result.started_at = timezone.now()
        result.save(update_fields=['started_at'])
    return result


def timing_for(student, lesson) -> dict:
    result = start_lesson(student, lesson)
    limit = lesson.time_limit_seconds
    deadline = result.started_at + timedelta(seconds=limit) if limit else None
    remaining = None
    if deadline is not None:
        remaining = max(0, int((deadline - timezone.now()).total_seconds()))
    return {
        'started_at': result.started_at,
        'time_limit_seconds': limit,
        'deadline': deadline,
        'remaining_seconds': remaining,
    }


def time_is_up(student, lesson) -> bool:
    if not lesson.time_limit_seconds:
        return False
    result = start_lesson(student, lesson)
    allowed = timedelta(seconds=lesson.time_limit_seconds + GRACE_SECONDS)
    return timezone.now() > result.started_at + allowed
