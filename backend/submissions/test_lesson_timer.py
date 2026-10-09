"""The lesson time limit is enforced by the server, not by the browser's countdown."""

from datetime import timedelta

from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from courses.models import Course, Dataset, Enrollment, Lesson, LessonExercise, Module
from submissions.models import UserResult
from users.models import User

SCHEMA = 'CREATE TABLE t (a INTEGER);'
SEED = 'INSERT INTO t VALUES (1), (2);'


class LessonTimerTests(APITestCase):
    def setUp(self):
        self.instructor = User.objects.create_user(
            email='t@test.com', password='x', role=User.Role.INSTRUCTOR, first_name='T', last_name='T')
        self.student = User.objects.create_user(
            email='s@test.com', password='x', role=User.Role.STUDENT, first_name='S', last_name='S')
        self.course = Course.objects.create(title='C', instructor=self.instructor,
                                            database_type='sqlite', is_published=True)
        Enrollment.objects.create(student=self.student, course=self.course)
        self.dataset = Dataset.objects.create(name='D', course=self.course, created_by=self.instructor,
                                              database_type='sqlite', schema_sql=SCHEMA, seed_sql=SEED)
        module = Module.objects.create(course=self.course, title='M', is_published=True)
        self.timed = self._lesson(module, 'Контрольна', time_limit_seconds=600)
        self.untimed = self._lesson(module, 'Практика', time_limit_seconds=None)
        self.client.force_authenticate(self.student)

    def _lesson(self, module, title, time_limit_seconds):
        lesson = Lesson.objects.create(course=self.course, module=module, title=title,
                                       lesson_type='practice', is_published=True,
                                       time_limit_seconds=time_limit_seconds)
        LessonExercise.objects.create(lesson=lesson, title='E', expected_query='SELECT a FROM t',
                                      dataset=self.dataset)
        return lesson

    def start(self, lesson):
        return self.client.post(f'/api/courses/{self.course.id}/lessons/{lesson.id}/start/')

    def submit(self, lesson):
        exercise = lesson.exercises.first()
        return self.client.post(
            f'/api/courses/{self.course.id}/lessons/{lesson.id}/submissions/',
            {'query': 'SELECT a FROM t', 'exercise_id': str(exercise.id)}, format='json')

    def test_start_returns_a_deadline_for_a_timed_lesson(self):
        resp = self.start(self.timed)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['time_limit_seconds'], 600)
        self.assertIsNotNone(resp.data['deadline'])
        self.assertTrue(0 < resp.data['remaining_seconds'] <= 600)

    def test_start_is_idempotent_so_a_page_refresh_does_not_reset_the_clock(self):
        first = self.start(self.timed).data['started_at']
        second = self.start(self.timed).data['started_at']
        self.assertEqual(first, second)
        self.assertEqual(UserResult.objects.filter(student=self.student, lesson=self.timed,
                                                   exercise=None).count(), 1)

    def test_untimed_lesson_has_no_deadline(self):
        resp = self.start(self.untimed)
        self.assertEqual(resp.status_code, 200)
        self.assertIsNone(resp.data['deadline'])
        self.assertIsNone(resp.data['time_limit_seconds'])

    def test_submission_within_the_limit_is_accepted(self):
        self.start(self.timed)
        resp = self.submit(self.timed)
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        self.assertTrue(resp.data['is_correct'])

    def test_submission_after_the_deadline_is_rejected(self):
        self.start(self.timed)
        row = UserResult.objects.get(student=self.student, lesson=self.timed, exercise=None)
        row.started_at = timezone.now() - timedelta(seconds=700)
        row.save(update_fields=['started_at'])

        resp = self.submit(self.timed)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp.data['code'], 'time_up')

    def test_grace_period_covers_the_last_seconds(self):
        self.start(self.timed)
        row = UserResult.objects.get(student=self.student, lesson=self.timed, exercise=None)
        row.started_at = timezone.now() - timedelta(seconds=604)
        row.save(update_fields=['started_at'])
        self.assertEqual(self.submit(self.timed).status_code, status.HTTP_201_CREATED)

    def test_first_submission_without_start_begins_the_clock(self):
        resp = self.submit(self.timed)
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        row = UserResult.objects.get(student=self.student, lesson=self.timed, exercise=None)
        self.assertIsNotNone(row.started_at)

    def test_untimed_lesson_accepts_submissions_any_time(self):
        self.start(self.untimed)
        row = UserResult.objects.get(student=self.student, lesson=self.untimed, exercise=None)
        row.started_at = timezone.now() - timedelta(days=30)
        row.save(update_fields=['started_at'])
        self.assertEqual(self.submit(self.untimed).status_code, status.HTTP_201_CREATED)

    def test_theory_lesson_cannot_be_started(self):
        theory = Lesson.objects.create(course=self.course, module=self.timed.module, title='Теорія',
                                       lesson_type='theory', is_published=True)
        self.assertEqual(self.start(theory).status_code, status.HTTP_400_BAD_REQUEST)

    def test_unenrolled_student_cannot_start(self):
        other = User.objects.create_user(email='o@test.com', password='x', role=User.Role.STUDENT,
                                         first_name='O', last_name='O')
        self.client.force_authenticate(other)
        self.assertEqual(self.start(self.timed).status_code, status.HTTP_403_FORBIDDEN)

    def test_instructor_preview_records_nothing(self):
        self.client.force_authenticate(self.instructor)
        resp = self.start(self.timed)
        self.assertEqual(resp.status_code, 200)
        self.assertIsNone(resp.data['deadline'])
        self.assertFalse(UserResult.objects.filter(lesson=self.timed, exercise=None).exists())
