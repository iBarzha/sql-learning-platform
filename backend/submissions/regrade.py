"""Grading setup shared by new answers and regrading of stored ones.

`SubmissionViewSet.create` and the regrade actions build the task and the runners
here, so an answer graded today and one regraded later are checked the same way.
"""

from __future__ import annotations

import logging
import time
from typing import Callable, NamedTuple, Union

from django.db import transaction
from django.db.models import F, Q
from django.utils import timezone

from grading.runner import build_task, make_runner, make_sequence_runner
from grading.service import GradingTask, RunFn, SequenceRunFn, grade as grade_submission

from .models import Submission, UserResult
from .storage import json_safe

logger = logging.getLogger(__name__)

LESSON_TIME_LIMIT = 600
ASSIGNMENT_TIME_LIMIT = 30
MAX_COUNT = 300
BUDGET_SECONDS = 25


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


def _exercise_spec(exercise, lesson):
    """Engine, time limit and task arguments of a lesson exercise."""
    return (
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
    )


def _assignment_spec(assignment):
    """Engine, time limit and task arguments of an assignment."""
    return (
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
    )


def grading_setup_for_exercise(exercise, lesson, *, user_id=None, submission_id=None,
                               dataset_id=None) -> GradingSetup:
    return _setup(
        *_exercise_spec(exercise, lesson),
        dict(user_id=user_id, submission_id=submission_id, dataset_id=dataset_id),
    )


def grading_setup_for_assignment(assignment, *, user_id=None, submission_id=None,
                                 dataset_id=None) -> GradingSetup:
    return _setup(
        *_assignment_spec(assignment),
        dict(user_id=user_id, submission_id=submission_id, dataset_id=dataset_id),
    )


def _attributed_setups(spec, dataset_id) -> Callable[[Submission], GradingSetup]:
    """Setups sharing one task whose student run is attributed to each regraded answer.

    The execution log then names the student and the answer, as it does for a new one.
    """
    db_type, time_limit, task_kwargs = spec
    base = _setup(db_type, time_limit, task_kwargs, {})

    def setup_for(submission) -> GradingSetup:
        return base._replace(runner=make_runner(
            db_type, time_limit,
            user_id=submission.student_id,
            submission_id=submission.id,
            dataset_id=dataset_id,
        ))

    return setup_for


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
    return {'submissions': 0, 'changed': 0, 'truncated': False, 'errors': 0}


def regrade_submissions(submissions_qs,
                        setup: Union[GradingSetup, Callable[[Submission], GradingSetup]], *,
                        reveal_rows: bool, max_count: int = MAX_COUNT,
                        budget_seconds: float = BUDGET_SECONDS) -> dict:
    """Regrade stored answers, least recently graded first, then rebuild their results.

    `setup` is one grading setup, or a function giving the setup of a submission when
    the answers belong to different exercises. Answers being graded right now are
    skipped. Every attempted answer counts toward `max_count`; once it or the time
    budget is exhausted the report says `truncated`, and the next call continues with
    the answers not reached, since the ones just regraded sort last. An answer whose
    grading raises is left as it was and counted in `errors`.
    """
    setup_for = setup if callable(setup) else (lambda submission: setup)
    report = _empty_report()
    deadline = time.monotonic() + budget_seconds
    touched = set()

    queryset = submissions_qs.exclude(status=Submission.Status.RUNNING).order_by(
        F('graded_at').asc(nulls_first=True), 'submitted_at', 'id')
    # One extra row tells a cut-off batch from one that ended exactly at the limit.
    candidates = list(queryset[:max(max_count, 0) + 1])
    for submission in candidates:
        attempted = report['submissions'] + report['errors']
        if attempted >= max_count or time.monotonic() >= deadline:
            report['truncated'] = True
            break
        before = (submission.score, submission.is_correct)
        try:
            grade_into(submission, setup_for(submission), reveal_rows=reveal_rows)
        except Exception:
            logger.exception('Regrading submission %s failed', submission.id)
            report['errors'] += 1
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
    """Rebuild the best score and completion of one result from its graded answers.

    The result row is locked so a new answer cannot update it in between. Attempts,
    the manual score and the timer extension are left untouched.
    """
    task = Q(exercise_id=exercise_id) if exercise_id else Q(assignment_id=assignment_id)
    with transaction.atomic():
        result = (UserResult.objects.select_for_update()
                  .filter(task, student_id=student_id).first())
        if result is None:
            return
        submissions = list(
            Submission.objects.filter(task, student_id=student_id)
            .exclude(status=Submission.Status.RUNNING)
            .order_by('submitted_at', 'id')
            .values('id', 'score', 'is_correct', 'submitted_at')
        )
        scored = [s for s in submissions if s['score'] is not None]
        best_score = max((s['score'] for s in scored), default=0)
        best = next((s for s in scored if s['score'] == best_score), None)
        first_correct = next((s for s in submissions if s['is_correct']), None)

        UserResult.objects.filter(pk=result.pk).update(
            best_score=best_score,
            best_submission_id=best['id'] if best else None,
            is_completed=first_correct is not None,
            first_completed_at=first_correct['submitted_at'] if first_correct else None,
        )


def regrade_lesson(lesson, exercises, *, max_count: int = MAX_COUNT,
                   budget_seconds: float = BUDGET_SECONDS) -> dict:
    """Regrade the answers to the given exercises of a lesson in one ordered pass."""
    exercises = {exercise.id: exercise for exercise in exercises}
    setups = {}

    def setup_for(submission):
        if submission.exercise_id not in setups:
            exercise = exercises[submission.exercise_id]
            setups[submission.exercise_id] = _attributed_setups(
                _exercise_spec(exercise, lesson), exercise.dataset_id)
        return setups[submission.exercise_id](submission)

    return regrade_submissions(
        Submission.objects.filter(exercise_id__in=list(exercises)), setup_for,
        reveal_rows=reveals_rows(lesson), max_count=max_count, budget_seconds=budget_seconds,
    )


def regrade_assignment(assignment, *, max_count: int = MAX_COUNT,
                       budget_seconds: float = BUDGET_SECONDS) -> dict:
    return regrade_submissions(
        assignment.submissions.all(),
        _attributed_setups(_assignment_spec(assignment), assignment.dataset_id),
        reveal_rows=True, max_count=max_count, budget_seconds=budget_seconds,
    )
