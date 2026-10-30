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


class InstructorTimerControlTests(APITestCase):
    """An instructor resets or extends one student's clock (problem 13)."""

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
        dataset = Dataset.objects.create(name='D', course=self.course, created_by=self.instructor,
                                         database_type='sqlite', schema_sql=SCHEMA, seed_sql=SEED)
        module = Module.objects.create(course=self.course, title='M', is_published=True)
        self.timed = Lesson.objects.create(course=self.course, module=module, title='Контрольна',
                                           lesson_type='practice', is_published=True,
                                           time_limit_seconds=600, order=2)
        self.second = Lesson.objects.create(course=self.course, module=module, title='Тест',
                                            lesson_type='practice', is_published=True,
                                            time_limit_seconds=300, order=1)
        self.untimed = Lesson.objects.create(course=self.course, module=module, title='Практика',
                                             lesson_type='practice', is_published=True, order=3)
        for lesson in (self.timed, self.second, self.untimed):
            LessonExercise.objects.create(lesson=lesson, title='E', expected_query='SELECT a FROM t',
                                          dataset=dataset)

    def control(self, lesson, user=None, **body):
        self.client.force_authenticate(user or self.instructor)
        body.setdefault('student', str(self.student.id))
        return self.client.post(f'/api/courses/{self.course.id}/lessons/{lesson.id}/timer/',
                                body, format='json')

    def started(self, seconds_ago):
        row, _ = UserResult.objects.get_or_create(student=self.student, lesson=self.timed,
                                                  exercise=None, assignment=None)
        row.started_at = timezone.now() - timedelta(seconds=seconds_ago)
        row.save(update_fields=['started_at'])
        return row

    def row(self):
        return UserResult.objects.get(student=self.student, lesson=self.timed, exercise=None)

    def test_reset_clears_the_start_and_the_extension(self):
        row = self.started(700)
        row.extra_seconds = 120
        row.save(update_fields=['extra_seconds'])

        resp = self.control(self.timed, action='reset')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertIsNone(resp.data['started_at'])
        self.assertIsNone(resp.data['deadline'])
        self.assertEqual(resp.data['extra_seconds'], 0)
        row = self.row()
        self.assertIsNone(row.started_at)
        self.assertEqual(row.extra_seconds, 0)

    def test_reset_without_a_row_is_a_no_op(self):
        resp = self.control(self.timed, action='reset')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertFalse(UserResult.objects.filter(lesson=self.timed, exercise=None).exists())

    def test_after_reset_the_student_can_answer_again(self):
        self.started(700)
        self.control(self.timed, action='reset')
        self.client.force_authenticate(self.student)
        exercise = self.timed.exercises.first()
        resp = self.client.post(
            f'/api/courses/{self.course.id}/lessons/{self.timed.id}/submissions/',
            {'query': 'SELECT a FROM t', 'exercise_id': str(exercise.id)}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)

    def test_extend_moves_the_deadline_and_time_is_up_honours_it(self):
        from submissions.timing import time_is_up

        row = self.started(700)
        before = row.started_at + timedelta(seconds=600)
        self.assertTrue(time_is_up(self.student, self.timed))

        resp = self.control(self.timed, action='extend', minutes=10)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['extra_seconds'], 600)
        self.assertEqual(resp.data['lesson_id'], str(self.timed.id))
        self.assertEqual(resp.data['time_limit_seconds'], 600)
        self.assertEqual(self.row().extra_seconds, 600)
        self.assertEqual(resp.data['deadline'], before + timedelta(minutes=10))
        self.assertFalse(time_is_up(self.student, self.timed))

        self.control(self.timed, action='extend', minutes=5)
        self.assertEqual(self.row().extra_seconds, 900)

    def test_extend_before_the_start_applies_once_the_student_starts(self):
        resp = self.control(self.timed, action='extend', minutes=10)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertIsNone(resp.data['started_at'])
        self.assertIsNone(resp.data['remaining_seconds'])

        self.client.force_authenticate(self.student)
        start = self.client.post(f'/api/courses/{self.course.id}/lessons/{self.timed.id}/start/')
        self.assertEqual(start.status_code, 200)
        self.assertEqual(start.data['extra_seconds'], 600)
        self.assertTrue(600 < start.data['remaining_seconds'] <= 1200)

    def test_minutes_out_of_range_or_missing_is_rejected(self):
        for body in ({'action': 'extend'}, {'action': 'extend', 'minutes': 0},
                     {'action': 'extend', 'minutes': 181}, {'action': 'pause'}):
            self.assertEqual(self.control(self.timed, **body).status_code,
                             status.HTTP_400_BAD_REQUEST, body)

    def test_lesson_without_a_limit_is_rejected(self):
        resp = self.control(self.untimed, action='extend', minutes=10)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(self.control(self.untimed, action='reset').status_code,
                         status.HTTP_400_BAD_REQUEST)

    def test_student_is_forbidden(self):
        resp = self.control(self.timed, user=self.student, action='extend', minutes=10)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_foreign_instructor_is_forbidden(self):
        resp = self.control(self.timed, user=self.foreign, action='reset')
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        self.client.force_authenticate(self.foreign)
        resp = self.client.get(f'/api/courses/{self.course.id}/timers/',
                               {'student': str(self.student.id)})
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_may_control_any_course(self):
        resp = self.control(self.timed, user=self.admin, action='extend', minutes=1)
        self.assertEqual(resp.status_code, 200, resp.data)

    def test_student_outside_the_course_is_not_found(self):
        other = User.objects.create_user(email='o@test.com', password='x', role=User.Role.STUDENT,
                                         first_name='O', last_name='O')
        resp = self.control(self.timed, student=str(other.id), action='extend', minutes=1)
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_timers_list_the_timed_lessons_in_order(self):
        self.started(100)
        self.client.force_authenticate(self.instructor)
        resp = self.client.get(f'/api/courses/{self.course.id}/timers/',
                               {'student': str(self.student.id)})
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual([e['lesson_id'] for e in resp.data],
                         [str(self.second.id), str(self.timed.id)])
        not_started, started = resp.data
        self.assertEqual(set(started), {'lesson_id', 'lesson_title', 'time_limit_seconds',
                                        'started_at', 'deadline', 'remaining_seconds',
                                        'extra_seconds'})
        self.assertIsNone(not_started['started_at'])
        self.assertIsNone(not_started['deadline'])
        self.assertIsNone(not_started['remaining_seconds'])
        self.assertEqual(not_started['time_limit_seconds'], 300)
        self.assertTrue(490 <= started['remaining_seconds'] <= 500)
        self.assertFalse(UserResult.objects.filter(lesson=self.second, exercise=None).exists())

    def test_timers_require_a_student(self):
        self.client.force_authenticate(self.instructor)
        resp = self.client.get(f'/api/courses/{self.course.id}/timers/')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_student_cannot_list_timers(self):
        self.client.force_authenticate(self.student)
        resp = self.client.get(f'/api/courses/{self.course.id}/timers/',
                               {'student': str(self.student.id)})
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
