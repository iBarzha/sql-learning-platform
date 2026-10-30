"""Regrading stored answers after the instructor fixes a reference (problem 14, part 1).

Runs on the in-memory SQLite sandbox, so the real grading path is exercised.
"""

from decimal import Decimal
from unittest import mock

from rest_framework import status
from rest_framework.test import APITestCase

from assignments.models import Assignment
from courses.models import Course, Dataset, Enrollment, Lesson, LessonExercise, Module
from submissions import regrade as regrade_module
from submissions.models import Submission, UserResult
from submissions.regrade import (
    grading_setup_for_exercise,
    regrade_lesson,
    regrade_submissions,
)
from users.models import User

SCHEMA = 'CREATE TABLE t (a INTEGER);'
SEED = 'INSERT INTO t VALUES (1), (2), (3);'
ALL_ROWS = 'SELECT a FROM t'
ABOVE_ONE = 'SELECT a FROM t WHERE a > 1'
NOTHING = 'SELECT a FROM t WHERE a > 100'


class RegradeTestCase(APITestCase):
    def setUp(self):
        self.instructor = User.objects.create_user(
            email='t@test.com', password='x', role=User.Role.INSTRUCTOR, first_name='T', last_name='T')
        self.foreign = User.objects.create_user(
            email='f@test.com', password='x', role=User.Role.INSTRUCTOR, first_name='F', last_name='F')
        self.admin = User.objects.create_user(
            email='a@test.com', password='x', role=User.Role.ADMIN, first_name='A', last_name='A')
        self.student = User.objects.create_user(
            email='s@test.com', password='x', role=User.Role.STUDENT, first_name='S', last_name='S')
        self.course = Course.objects.create(title='C', instructor=self.instructor,
                                            database_type='sqlite', is_published=True)
        Enrollment.objects.create(student=self.student, course=self.course)
        self.dataset = Dataset.objects.create(name='D', course=self.course, created_by=self.instructor,
                                              database_type='sqlite', schema_sql=SCHEMA, seed_sql=SEED)
        self.module = Module.objects.create(course=self.course, title='M', is_published=True)
        self.lesson = Lesson.objects.create(course=self.course, module=self.module, title='L',
                                            lesson_type='practice', is_published=True)
        self.exercise = LessonExercise.objects.create(
            lesson=self.lesson, title='E1', expected_query=ALL_ROWS, dataset=self.dataset, order=1)
        self.other_exercise = LessonExercise.objects.create(
            lesson=self.lesson, title='E2', expected_query=ALL_ROWS, dataset=self.dataset, order=2)

    def submit(self, query, exercise=None):
        self.client.force_authenticate(self.student)
        exercise = exercise or self.exercise
        resp = self.client.post(
            f'/api/courses/{self.course.id}/lessons/{self.lesson.id}/submissions/',
            {'query': query, 'exercise_id': str(exercise.id)}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        return Submission.objects.get(id=resp.data['id'])

    def regrade(self, user=None, body=None):
        self.client.force_authenticate(user or self.instructor)
        return self.client.post(
            f'/api/courses/{self.course.id}/lessons/{self.lesson.id}/regrade/',
            body or {}, format='json')

    def set_reference(self, exercise, query):
        exercise.expected_query = query
        exercise.save(update_fields=['expected_query'])

    def result(self, exercise=None):
        return UserResult.objects.get(student=self.student, exercise=exercise or self.exercise)

    def test_a_fixed_reference_flips_both_answers(self):
        right = self.submit(ALL_ROWS)
        wrong = self.submit(ABOVE_ONE)
        before = self.result()
        self.assertTrue(right.is_correct)
        self.assertFalse(wrong.is_correct)
        self.assertEqual(before.best_submission_id, right.id)

        self.set_reference(self.exercise, ABOVE_ONE)
        resp = self.regrade()
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data, {'submissions': 2, 'changed': 2, 'truncated': False, 'errors': 0})

        right.refresh_from_db()
        wrong.refresh_from_db()
        self.assertFalse(right.is_correct)
        self.assertEqual(right.score, Decimal('0'))
        self.assertTrue(wrong.is_correct)
        self.assertEqual(wrong.score, Decimal('100'))

        after = self.result()
        self.assertEqual(after.total_attempts, 2)
        self.assertEqual(after.best_submission_id, wrong.id)
        self.assertEqual(after.best_score, Decimal('100'))
        self.assertTrue(after.is_completed)
        self.assertEqual(after.first_completed_at, wrong.submitted_at)

    def test_completion_is_withdrawn_when_no_answer_matches_any_more(self):
        self.submit(ALL_ROWS)
        result = self.result()
        result.manual_score = Decimal('40')
        result.manual_comment = 'частково'
        result.save(update_fields=['manual_score', 'manual_comment'])

        self.set_reference(self.exercise, NOTHING)
        resp = self.regrade()
        self.assertEqual(resp.data['changed'], 1)

        result = self.result()
        self.assertFalse(result.is_completed)
        self.assertIsNone(result.first_completed_at)
        self.assertEqual(result.best_score, Decimal('0'))
        self.assertEqual(result.total_attempts, 1)
        self.assertEqual(result.manual_score, Decimal('40'))
        self.assertEqual(result.manual_comment, 'частково')

    def test_an_unchanged_reference_changes_nothing(self):
        self.submit(ALL_ROWS)
        self.submit(ABOVE_ONE)
        resp = self.regrade()
        self.assertEqual(resp.data, {'submissions': 2, 'changed': 0, 'truncated': False, 'errors': 0})

    def test_exercise_id_limits_the_regrade_to_one_exercise(self):
        self.submit(ALL_ROWS)
        other = self.submit(ALL_ROWS, self.other_exercise)
        self.set_reference(self.other_exercise, NOTHING)
        self.set_reference(self.exercise, NOTHING)

        resp = self.regrade(body={'exercise_id': str(self.other_exercise.id)})
        self.assertEqual(resp.data, {'submissions': 1, 'changed': 1, 'truncated': False, 'errors': 0})
        other.refresh_from_db()
        self.assertFalse(other.is_correct)
        self.assertTrue(self.result().is_completed)
        self.assertFalse(self.result(self.other_exercise).is_completed)

    def test_unknown_exercise_is_not_found(self):
        foreign_lesson = Lesson.objects.create(course=self.course, module=self.module, title='X',
                                              lesson_type='practice')
        stray = LessonExercise.objects.create(lesson=foreign_lesson, title='X',
                                              expected_query=ALL_ROWS, dataset=self.dataset)
        resp = self.regrade(body={'exercise_id': str(stray.id)})
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_count_limit_truncates_and_keeps_the_rest(self):
        first = self.submit(ALL_ROWS)
        second = self.submit(ALL_ROWS)
        self.set_reference(self.exercise, NOTHING)
        self.exercise.refresh_from_db()

        report = regrade_submissions(
            self.exercise.submissions.all(),
            grading_setup_for_exercise(self.exercise, self.lesson),
            reveal_rows=True, max_count=1,
        )
        self.assertEqual(report, {'submissions': 1, 'changed': 1, 'truncated': True, 'errors': 0})
        first.refresh_from_db()
        second.refresh_from_db()
        self.assertFalse(first.is_correct)
        self.assertTrue(second.is_correct)
        result = self.result()
        self.assertEqual(result.best_submission_id, second.id)
        self.assertEqual(result.first_completed_at, second.submitted_at)

    def test_exhausted_budget_truncates(self):
        self.submit(ALL_ROWS)
        report = regrade_submissions(
            self.exercise.submissions.all(),
            grading_setup_for_exercise(self.exercise, self.lesson),
            reveal_rows=True, budget_seconds=0,
        )
        self.assertEqual(report, {'submissions': 0, 'changed': 0, 'truncated': True, 'errors': 0})

    def test_a_truncated_regrade_continues_with_the_rest(self):
        first = self.submit(ALL_ROWS)
        second = self.submit(ALL_ROWS, self.other_exercise)
        self.set_reference(self.exercise, NOTHING)
        self.set_reference(self.other_exercise, NOTHING)
        exercises = list(self.lesson.exercises.select_related('dataset'))

        one = regrade_lesson(self.lesson, exercises, max_count=1)
        two = regrade_lesson(self.lesson, exercises, max_count=1)
        self.assertEqual(one, {'submissions': 1, 'changed': 1, 'truncated': True, 'errors': 0})
        self.assertEqual(two['changed'], 1)
        first.refresh_from_db()
        second.refresh_from_db()
        self.assertFalse(first.is_correct)
        self.assertFalse(second.is_correct)
        self.assertFalse(self.result().is_completed)
        self.assertFalse(self.result(self.other_exercise).is_completed)

    def test_grading_failures_count_toward_the_limit(self):
        first = self.submit(ALL_ROWS)
        self.submit(ALL_ROWS)
        with mock.patch('submissions.regrade.grade_submission', side_effect=RuntimeError('boom')),                 self.assertLogs('submissions.regrade', level='ERROR'):
            report = regrade_submissions(
                self.exercise.submissions.all(),
                grading_setup_for_exercise(self.exercise, self.lesson),
                reveal_rows=True, max_count=1,
            )
        self.assertEqual(report, {'submissions': 0, 'changed': 0, 'truncated': True, 'errors': 1})
        first.refresh_from_db()
        self.assertTrue(first.is_correct)
        self.assertTrue(self.result().is_completed)

    def test_regraded_runs_are_attributed_to_the_answer(self):
        answer = self.submit(ALL_ROWS)
        calls = []
        real = regrade_module.make_runner

        def recording(db_type, timeout, **attribution):
            calls.append(attribution)
            return real(db_type, timeout, **attribution)

        with mock.patch('submissions.regrade.make_runner', recording):
            self.assertEqual(self.regrade().status_code, status.HTTP_200_OK)
        self.assertIn({'user_id': self.student.id, 'submission_id': answer.id,
                       'dataset_id': self.dataset.id}, calls)

    def test_answers_being_graded_are_left_alone(self):
        running = self.submit(ALL_ROWS)
        Submission.objects.filter(pk=running.pk).update(status=Submission.Status.RUNNING)
        self.set_reference(self.exercise, NOTHING)
        resp = self.regrade()
        self.assertEqual(resp.data['submissions'], 0)
        running.refresh_from_db()
        self.assertTrue(running.is_correct)

    def test_student_is_forbidden(self):
        self.assertEqual(self.regrade(user=self.student).status_code, status.HTTP_403_FORBIDDEN)

    def test_foreign_instructor_is_forbidden(self):
        self.assertEqual(self.regrade(user=self.foreign).status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_may_regrade(self):
        self.assertEqual(self.regrade(user=self.admin).status_code, status.HTTP_200_OK)


class AssignmentRegradeTestCase(APITestCase):
    def setUp(self):
        self.instructor = User.objects.create_user(
            email='t@test.com', password='x', role=User.Role.INSTRUCTOR, first_name='T', last_name='T')
        self.foreign = User.objects.create_user(
            email='f@test.com', password='x', role=User.Role.INSTRUCTOR, first_name='F', last_name='F')
        self.student = User.objects.create_user(
            email='s@test.com', password='x', role=User.Role.STUDENT, first_name='S', last_name='S')
        self.course = Course.objects.create(title='C', instructor=self.instructor,
                                            database_type='sqlite', is_published=True)
        Enrollment.objects.create(student=self.student, course=self.course)
        dataset = Dataset.objects.create(name='D', course=self.course, created_by=self.instructor,
                                         database_type='sqlite', schema_sql=SCHEMA, seed_sql=SEED)
        self.assignment = Assignment.objects.create(
            course=self.course, dataset=dataset, title='A', description='d',
            expected_query=ALL_ROWS, is_published=True)
        self.url = f'/api/courses/{self.course.id}/assignments/{self.assignment.id}/'

    def submit(self, query):
        self.client.force_authenticate(self.student)
        resp = self.client.post(f'{self.url}submissions/', {'query': query}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        return Submission.objects.get(id=resp.data['id'])

    def regrade(self, user=None):
        self.client.force_authenticate(user or self.instructor)
        return self.client.post(f'{self.url}regrade/')

    def test_a_fixed_reference_flips_both_answers(self):
        right = self.submit(ALL_ROWS)
        wrong = self.submit(ABOVE_ONE)
        self.assignment.expected_query = ABOVE_ONE
        self.assignment.save(update_fields=['expected_query'])

        resp = self.regrade()
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data, {'submissions': 2, 'changed': 2, 'truncated': False, 'errors': 0})
        right.refresh_from_db()
        wrong.refresh_from_db()
        self.assertFalse(right.is_correct)
        self.assertTrue(wrong.is_correct)
        result = UserResult.objects.get(student=self.student, assignment=self.assignment)
        self.assertEqual(result.total_attempts, 2)
        self.assertEqual(result.best_submission_id, wrong.id)
        self.assertEqual(result.first_completed_at, wrong.submitted_at)

    def test_regraded_runs_are_attributed_to_the_answer(self):
        answer = self.submit(ALL_ROWS)
        calls = []
        real = regrade_module.make_runner

        def recording(db_type, timeout, **attribution):
            calls.append(attribution)
            return real(db_type, timeout, **attribution)

        with mock.patch('submissions.regrade.make_runner', recording):
            self.assertEqual(self.regrade().status_code, status.HTTP_200_OK)
        self.assertIn({'user_id': self.student.id, 'submission_id': answer.id,
                       'dataset_id': self.assignment.dataset_id}, calls)

    def test_student_and_foreign_instructor_are_forbidden(self):
        self.assertEqual(self.regrade(user=self.student).status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(self.regrade(user=self.foreign).status_code, status.HTTP_403_FORBIDDEN)


class ResultUpdateRaceTestCase(APITestCase):
    """A new answer is compared with the stored result, not with the one loaded earlier."""

    setUp = RegradeTestCase.setUp

    def answer(self, score, correct=False):
        return Submission.objects.create(
            student=self.student, lesson=self.lesson, exercise=self.exercise, query=ALL_ROWS,
            status=Submission.Status.COMPLETED,
            score=None if score is None else Decimal(score), is_correct=correct)

    def loaded_result(self, best, best_submission=None, completed=False):
        result = UserResult.objects.create(
            student=self.student, lesson=self.lesson, exercise=self.exercise,
            best_score=Decimal(best), best_submission=best_submission, is_completed=completed)
        return UserResult.objects.get(pk=result.pk)

    def test_a_higher_score_wins_after_a_concurrent_regrade_lowered_the_best(self):
        old = self.answer('80')
        result = self.loaded_result('80', old)
        # A regrade lowers the stored best after this result was loaded.
        UserResult.objects.filter(pk=result.pk).update(best_score=Decimal('0'), best_submission=None)
        new = self.answer('50')
        result.update_from_submission(new)
        self.assertEqual(result.best_score, Decimal('50'))
        self.assertEqual(result.best_submission_id, new.id)
        self.assertEqual(result.total_attempts, 1)

    def test_completion_is_recorded_after_a_concurrent_regrade_withdrew_it(self):
        result = self.loaded_result('0', completed=True)
        UserResult.objects.filter(pk=result.pk).update(is_completed=False)
        new = self.answer('100', correct=True)
        result.update_from_submission(new)
        self.assertTrue(result.is_completed)
        self.assertEqual(result.first_completed_at, new.submitted_at)

    def test_a_lower_stored_value_in_memory_does_not_override_the_database(self):
        best = self.answer('90')
        result = self.loaded_result('0')
        UserResult.objects.filter(pk=result.pk).update(best_score=Decimal('90'), best_submission=best)
        result.update_from_submission(self.answer('50'))
        self.assertEqual(result.best_score, Decimal('90'))
        self.assertEqual(result.best_submission_id, best.id)

    def test_a_tie_never_replaces_the_best(self):
        best = self.answer('50')
        result = self.loaded_result('50', best)
        result.update_from_submission(self.answer('50'))
        self.assertEqual(result.best_submission_id, best.id)

    def test_a_zero_or_missing_score_never_becomes_the_best(self):
        result = self.loaded_result('0')
        result.update_from_submission(self.answer('0'))
        result.update_from_submission(self.answer(None))
        self.assertIsNone(result.best_submission_id)
        self.assertEqual(result.best_score, Decimal('0'))
        self.assertEqual(result.total_attempts, 2)
