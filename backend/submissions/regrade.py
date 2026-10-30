"""Grading setup shared by new answers and regrading of stored ones.

`SubmissionViewSet.create` and the regrade actions build the task and the runners
here, so an answer graded today and one regraded later are checked the same way.
"""

from __future__ import annotations

import logging
import time
from typing import NamedTuple

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from grading.runner import build_task, make_runner, make_sequence_runner
from grading.service import GradingTask, RunFn, SequenceRunFn, grade as grade_submission

from .models import Submission, UserResult
from .storage import json_safe

logger = logging.getLogger(__name__)

LESSON_TIME_LIMIT = 600
ASSIGNMENT_TIME_LIMIT = 30
MAX_COUNT = 300
BUDGET_SECONDS = 60


class GradingSetup(NamedTuple):
    task: GradingTask
    runner: RunFn
    sequence_runner: SequenceRunFn


def _setup(db_type, time_limit, task_kwargs, attribution) -> GradingSetup:
    return GradingSetup(
        build_task(db_type, **task_kwargs),
        make_runner(db_type, time_limit, **attribution),
        make_sequence_runner(db_type, time_limit),
    )


def grading_setup_for_exercise(exercise, lesson, *, user_id=None, submission_id=None,
                               dataset_id=None) -> GradingSetup:
    return _setup(
        lesson.course.database_type,
        lesson.time_limit_seconds or LESSON_TIME_LIMIT,
        dict(
            reference_query=exercise.expected_query,
            dataset=exercise.dataset,
            check_datasets=exercise.check_datasets or [],
            required_keywords=exercise.required_keywords or [],
            forbidden_keywords=exercise.forbidden_keywords or [],
            order_matters=exercise.order_matters,
            max_score=exercise.max_score,
            query_type='select',
            expected_result=exercise.expected_result,
            criteria=exercise.criteria or {},
            ignore_column_order=exercise.ignore_column_order,
        ),
        dict(user_id=user_id, submission_id=submission_id, dataset_id=dataset_id),
    )


def grading_setup_for_assignment(assignment, *, user_id=None, submission_id=None,
                                 dataset_id=None) -> GradingSetup:
    return _setup(
        assignment.course.database_type,
        assignment.time_limit_seconds or ASSIGNMENT_TIME_LIMIT,
        dict(
            reference_query=assignment.expected_query,
            dataset=assignment.dataset,
            check_datasets=assignment.check_datasets or [],
            required_keywords=assignment.required_keywords or [],
            forbidden_keywords=assignment.forbidden_keywords or [],
            order_matters=assignment.order_matters,
            max_score=assignment.max_score,
            query_type=assignment.query_type,
            expected_result=assignment.expected_result,
            criteria=assignment.criteria or {},
            ignore_column_order=assignment.ignore_column_order,
        ),
        dict(user_id=user_id, submission_id=submission_id, dataset_id=dataset_id),
    )


def reveals_rows(lesson) -> bool:
    """A timed lesson is a test: the reference rows would hand out the answer."""
    return not (lesson is not None and bool(lesson.time_limit_seconds))


def grade_into(submission, setup: GradingSetup, *, reveal_rows: bool) -> None:
    """Grade `submission.query` and store the outcome on the instance (not saved)."""
    graded = grade_submission(
        setup.task, submission.query, setup.runner,
        run_sequence=setup.sequence_runner,
        reveal_rows=reveal_rows,
    )
    execution = graded.execution

    submission.execution_time_ms = execution.execution_time_ms
    if execution.success:
        submission.status = Submission.Status.COMPLETED
        submission.error_message = ''
        submission.result = {
            'success': True,
            'columns': json_safe(execution.columns),
            'rows': json_safe(execution.rows),
            'row_count': len(execution.rows),
            'affected_rows': execution.affected_rows,
            'execution_time_ms': execution.execution_time_ms,
            'error_message': '',
            'truncated': execution.truncated,
        }
    else:
        submission.status = Submission.Status.ERROR
        submission.error_message = execution.error
        submission.result = {'success': False, 'error_message': execution.error}

    submission.score = graded.score
    submission.is_correct = graded.passed
    submission.feedback = json_safe(graded.feedback)
    submission.graded_at = timezone.now()


def _empty_report() -> dict:
    return {'submissions': 0, 'changed': 0, 'truncated': False}


def regrade_submissions(submissions_qs, setup: GradingSetup, *, reveal_rows: bool,
                        max_count: int = MAX_COUNT,
                        budget_seconds: float = BUDGET_SECONDS) -> dict:
    """Regrade stored answers oldest first, then rebuild the results they feed.

    Stops after `max_count` answers or once `budget_seconds` have passed and reports
    `truncated`; the answers not reached keep their previous grade. An answer whose
    grading raises is left as it was.
    """
    report = _empty_report()
    deadline = time.monotonic() + budget_seconds
    touched = set()

    # One extra row tells a cut-off batch from one that ended exactly at the limit.
    candidates = list(submissions_qs.order_by('submitted_at', 'id')[:max(max_count, 0) + 1])
    for submission in candidates:
        if report['submissions'] >= max_count or time.monotonic() >= deadline:
            report['truncated'] = True
            break
        before = (submission.score, submission.is_correct)
        try:
            grade_into(submission, setup, reveal_rows=reveal_rows)
        except Exception:
            logger.exception('Regrading submission %s failed', submission.id)
            continue
        with transaction.atomic():
            submission.save()
        report['submissions'] += 1
        if (submission.score, submission.is_correct) != before:
            report['changed'] += 1
        touched.add((submission.student_id, submission.assignment_id, submission.exercise_id))

    for student_id, assignment_id, exercise_id in touched:
        recompute_result(student_id, assignment_id=assignment_id, exercise_id=exercise_id)
    return report


def recompute_result(student_id, *, assignment_id=None, exercise_id=None) -> None:
    """Rebuild the best score and completion of one result from all its answers.

    Attempts, the manual score and the timer extension are left untouched.
    """
    task = Q(exercise_id=exercise_id) if exercise_id else Q(assignment_id=assignment_id)
    submissions = list(
        Submission.objects.filter(task, student_id=student_id)
        .order_by('submitted_at', 'id')
        .values('id', 'score', 'is_correct', 'submitted_at')
    )
    scored = [s for s in submissions if s['score'] is not None]
    best_score = max((s['score'] for s in scored), default=0)
    best = next((s for s in scored if s['score'] == best_score), None)
    first_correct = next((s for s in submissions if s['is_correct']), None)

    results = UserResult.objects.filter(student_id=student_id)
    results = (results.filter(exercise_id=exercise_id) if exercise_id
               else results.filter(assignment_id=assignment_id))
    results.update(
        best_score=best_score,
        best_submission_id=best['id'] if best else None,
        is_completed=first_correct is not None,
        first_completed_at=first_correct['submitted_at'] if first_correct else None,
    )


def _regrade_all(jobs, *, reveal_rows, max_count, budget_seconds) -> dict:
    """Regrade several (queryset, setup) pairs under one count and time budget."""
    report = _empty_report()
    deadline = time.monotonic() + budget_seconds
    for submissions_qs, setup in jobs:
        part = regrade_submissions(
            submissions_qs, setup, reveal_rows=reveal_rows,
            max_count=max_count - report['submissions'],
            budget_seconds=deadline - time.monotonic(),
        )
        report['submissions'] += part['submissions']
        report['changed'] += part['changed']
        if part['truncated']:
            report['truncated'] = True
            break
    return report


def regrade_lesson(lesson, exercises, *, max_count: int = MAX_COUNT,
                   budget_seconds: float = BUDGET_SECONDS) -> dict:
    jobs = (
        (exercise.submissions.all(), grading_setup_for_exercise(exercise, lesson))
        for exercise in exercises
    )
    return _regrade_all(jobs, reveal_rows=reveals_rows(lesson),
                        max_count=max_count, budget_seconds=budget_seconds)


def regrade_assignment(assignment, *, max_count: int = MAX_COUNT,
                       budget_seconds: float = BUDGET_SECONDS) -> dict:
    return regrade_submissions(
        assignment.submissions.all(), grading_setup_for_assignment(assignment),
        reveal_rows=True, max_count=max_count, budget_seconds=budget_seconds,
    )
