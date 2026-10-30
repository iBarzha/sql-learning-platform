"""Server-side lesson timer.

The countdown a student sees is only a display; what counts is the moment recorded
here when they first open the practice, and the deadline derived from it.
"""

from datetime import timedelta

from django.db.models import F
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


def _timer_row(student, lesson):
    return UserResult.objects.filter(
        student=student, lesson=lesson, exercise=None, assignment=None,
    ).first()


def _timing(lesson, result) -> dict:
    """Deadline of a lesson-level row; nothing is started when the row is absent."""
    limit = lesson.time_limit_seconds
    started_at = result.started_at if result is not None else None
    extra = result.extra_seconds if result is not None else 0
    deadline = remaining = None
    if limit and started_at is not None:
        deadline = started_at + timedelta(seconds=limit + extra)
        remaining = max(0, int((deadline - timezone.now()).total_seconds()))
    return {
        'started_at': started_at,
        'time_limit_seconds': limit,
        'deadline': deadline,
        'remaining_seconds': remaining,
        'extra_seconds': extra,
    }


def timing_for(student, lesson) -> dict:
    return _timing(lesson, start_lesson(student, lesson))


def time_is_up(student, lesson) -> bool:
    if not lesson.time_limit_seconds:
        return False
    result = start_lesson(student, lesson)
    allowed = timedelta(seconds=lesson.time_limit_seconds + result.extra_seconds + GRACE_SECONDS)
    return timezone.now() > result.started_at + allowed


# Instructor side: inspect, reset and extend a student's clock without starting it.

def timer_entry(lesson, result) -> dict:
    return {'lesson_id': str(lesson.id), 'lesson_title': lesson.title, **_timing(lesson, result)}


def course_timers(student, lessons) -> list[dict]:
    """One entry per lesson, in the given order; `lessons` should be the timed ones."""
    lessons = list(lessons)
    rows = {
        row.lesson_id: row
        for row in UserResult.objects.filter(
            student=student, lesson__in=lessons, exercise=None, assignment=None,
        )
    }
    return [timer_entry(lesson, rows.get(lesson.id)) for lesson in lessons]


def reset_timer(student, lesson) -> dict:
    """Forget the start and any extension; the clock restarts when the student opens the lesson."""
    UserResult.objects.filter(
        student=student, lesson=lesson, exercise=None, assignment=None,
    ).update(started_at=None, extra_seconds=0)
    return timer_entry(lesson, _timer_row(student, lesson))


def extend_timer(student, lesson, minutes: int) -> dict:
    """Add time; a student who has not started yet gets it once they start."""
    result, _ = UserResult.objects.get_or_create(
        student=student, lesson=lesson, exercise=None, assignment=None,
        defaults={'started_at': None},
    )
    UserResult.objects.filter(pk=result.pk).update(
        extra_seconds=F('extra_seconds') + minutes * 60,
    )
    result.refresh_from_db()
    return timer_entry(lesson, result)
