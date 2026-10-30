"""Course progress counted over every published task, not only the ones a student tried."""

from decimal import Decimal

from django.db.models import Q

from assignments.models import Assignment
from courses.models import LessonExercise
from .models import UserResult

PRACTICE_LESSON_TYPES = ('practice', 'mixed')


def _rate(part, whole):
    return round(part / whole * 100, 2) if whole > 0 else 0


def course_progress(student, courses) -> list[dict]:
    """One progress entry per course, in the given order.

    Tasks are the published assignments plus the exercises of published practice and
    mixed lessons. The whole computation takes four queries whatever the course count.
    """
    courses = list(courses)
    course_ids = [course.id for course in courses]

    assignment_tasks = {
        row['id']: (row['course_id'], row['max_score'])
        for row in Assignment.objects.filter(
            course_id__in=course_ids, is_published=True,
        ).values('id', 'course_id', 'max_score')
    }
    exercise_tasks = {
        row['id']: (row['lesson__course_id'], row['max_score'])
        for row in LessonExercise.objects.filter(
            lesson__course_id__in=course_ids,
            lesson__is_published=True,
            lesson__lesson_type__in=PRACTICE_LESSON_TYPES,
        ).values('id', 'lesson__course_id', 'max_score')
    }

    totals = {cid: {'tasks': 0, 'max': 0, 'completed': 0, 'score': Decimal(0)}
              for cid in course_ids}
    for course_id, max_score in [*assignment_tasks.values(), *exercise_tasks.values()]:
        totals[course_id]['tasks'] += 1
        totals[course_id]['max'] += max_score

    results = UserResult.objects.filter(student=student).filter(
        Q(assignment_id__in=list(assignment_tasks)) | Q(exercise_id__in=list(exercise_tasks))
    )
    for result in results:
        task = (assignment_tasks.get(result.assignment_id) if result.assignment_id
                else exercise_tasks.get(result.exercise_id))
        if task is None:
            continue
        entry = totals[task[0]]
        if result.is_completed:
            entry['completed'] += 1
        entry['score'] += result.effective_score

    progress = []
    for course in courses:
        entry = totals[course.id]
        total_score = float(entry['score'])
        progress.append({
            'course_id': str(course.id),
            'course_title': course.title,
            'total_assignments': entry['tasks'],
            'completed_assignments': entry['completed'],
            'total_score': total_score,
            'max_possible_score': entry['max'],
            'completion_rate': _rate(entry['completed'], entry['tasks']),
            'percentage_score': _rate(total_score, entry['max']),
        })
    return progress
