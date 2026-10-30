"""The instructor's manual score overrides the automatic one (problem 14, part 2)."""

from decimal import Decimal

from rest_framework import status
from rest_framework.test import APITestCase

from assignments.models import Assignment
from courses.models import Course, Enrollment, Lesson, LessonExercise, Module
from submissions.models import UserResult
from users.models import User


class ManualScoreTests(APITestCase):
    def setUp(self):
        self.instructor = User.objects.create_user(
            email='t@test.com', password='x', role=User.Role.INSTRUCTOR, first_name='T', last_name='T')
        self.foreign = User.objects.create_user(
            email='f@test.com', password='x', role=User.Role.INSTRUCTOR, first_name='F', last_name='F')
        self.admin = User.objects.create_user(
            email='a@test.com', password='x', role=User.Role.ADMIN, first_name='A', last_name='A')
        self.student = User.objects.create_user(
            email='s@test.com', password='x', role=User.Role.STUDENT, first_name='S', last_name='S')
        self.other_student = User.objects.create_user(
            email='o@test.com', password='x', role=User.Role.STUDENT, first_name='O', last_name='O')
        self.course = Course.objects.create(title='C', instructor=self.instructor,
                                            database_type='sqlite', is_published=True)
        for student in (self.student, self.other_student):
            Enrollment.objects.create(student=student, course=self.course)
        module = Module.objects.create(course=self.course, title='M', is_published=True)
        self.lesson = Lesson.objects.create(course=self.course, module=module, title='Урок',
                                            lesson_type='practice', is_published=True)
        self.exercise = LessonExercise.objects.create(lesson=self.lesson, title='Вправа',
                                                      expected_query='SELECT 1', max_score=100)
        self.result = UserResult.objects.create(
            student=self.student, lesson=self.lesson, exercise=self.exercise,
            best_score=Decimal('0'), total_attempts=2)
        self.other_result = UserResult.objects.create(
            student=self.other_student, lesson=self.lesson, exercise=self.exercise,
            best_score=Decimal('100'), is_completed=True, total_attempts=1)

    def patch(self, body, user=None, result=None):
        self.client.force_authenticate(user or self.instructor)
        return self.client.patch(f'/api/results/{(result or self.result).id}/', body, format='json')

    def test_owner_sets_a_manual_score(self):
        resp = self.patch({'manual_score': 85, 'manual_comment': 'Логіка правильна'})
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(Decimal(resp.data['manual_score']), Decimal('85'))
        self.assertEqual(Decimal(resp.data['effective_score']), Decimal('85'))
        self.assertEqual(Decimal(resp.data['best_score']), Decimal('0'))
        self.assertEqual(resp.data['manual_comment'], 'Логіка правильна')
        self.assertEqual(resp.data['max_score'], 100)
        self.assertEqual(resp.data['exercise_title'], 'Вправа')
        self.assertEqual(resp.data['lesson_title'], 'Урок')
        self.assertIsNotNone(resp.data['manual_set_at'])

        self.result.refresh_from_db()
        self.assertEqual(self.result.manual_score, Decimal('85'))
        self.assertEqual(self.result.manual_set_by, self.instructor)
        self.assertEqual(self.result.effective_score, Decimal('85'))
        self.assertEqual(self.result.total_attempts, 2)

    def test_admin_may_set_a_manual_score(self):
        self.assertEqual(self.patch({'manual_score': 10}, user=self.admin).status_code, 200)

    def test_student_is_forbidden(self):
        resp = self.patch({'manual_score': 100}, user=self.student)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        self.result.refresh_from_db()
        self.assertIsNone(self.result.manual_score)

    def test_foreign_instructor_is_forbidden(self):
        resp = self.patch({'manual_score': 100}, user=self.foreign)
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_score_above_the_maximum_is_rejected(self):
        self.assertEqual(self.patch({'manual_score': 101}).status_code,
                         status.HTTP_400_BAD_REQUEST)
        self.assertEqual(self.patch({'manual_score': -1}).status_code,
                         status.HTTP_400_BAD_REQUEST)
        self.assertEqual(self.patch({'manual_score': 100}).status_code, status.HTTP_200_OK)

    def test_assignment_maximum_applies_to_assignment_results(self):
        assignment = Assignment.objects.create(course=self.course, title='A', description='d',
                                               expected_query='SELECT 1', is_published=True,
                                               max_score=20)
        result = UserResult.objects.create(student=self.student, assignment=assignment)
        self.assertEqual(self.patch({'manual_score': 25}, result=result).status_code,
                         status.HTTP_400_BAD_REQUEST)
        resp = self.patch({'manual_score': 20}, result=result)
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['assignment_title'], 'A')

    def test_null_clears_the_override(self):
        self.patch({'manual_score': 85, 'manual_comment': 'x'})
        resp = self.patch({'manual_score': None, 'manual_comment': ''})
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertIsNone(resp.data['manual_score'])
        self.assertIsNone(resp.data['manual_set_at'])
        self.assertEqual(Decimal(resp.data['effective_score']), Decimal('0'))
        self.result.refresh_from_db()
        self.assertIsNone(self.result.manual_set_by)

    def test_only_manual_fields_can_change(self):
        resp = self.patch({'best_score': 100, 'is_completed': True, 'manual_score': 5})
        self.assertEqual(resp.status_code, 200, resp.data)
        self.result.refresh_from_db()
        self.assertEqual(self.result.best_score, Decimal('0'))
        self.assertFalse(self.result.is_completed)

    def test_put_and_delete_are_not_allowed(self):
        self.client.force_authenticate(self.instructor)
        url = f'/api/results/{self.result.id}/'
        self.assertEqual(self.client.put(url, {}, format='json').status_code,
                         status.HTTP_405_METHOD_NOT_ALLOWED)
        self.assertEqual(self.client.delete(url).status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_progress_uses_the_manual_score(self):
        self.patch({'manual_score': 60})
        self.client.force_authenticate(self.student)
        resp = self.client.get('/api/results/my_progress/', {'course': str(self.course.id)})
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data[0]['total_score'], 60.0)

    def test_lesson_total_uses_the_manual_score(self):
        self.patch({'manual_score': 70})
        self.client.force_authenticate(self.student)
        resp = self.client.get(f'/api/courses/{self.course.id}/lessons/')
        self.assertEqual(resp.status_code, 200, resp.data)
        lesson = next(item for item in self.rows(resp) if item['id'] == str(self.lesson.id))
        self.assertEqual(Decimal(str(lesson['user_best_score'])), Decimal('70'))

    def test_assignment_score_uses_the_manual_score(self):
        assignment = Assignment.objects.create(course=self.course, title='A', description='d',
                                               expected_query='SELECT 1', is_published=True)
        result = UserResult.objects.create(student=self.student, assignment=assignment,
                                           best_score=Decimal('0'))
        self.patch({'manual_score': 30}, result=result)
        self.client.force_authenticate(self.student)
        resp = self.client.get(f'/api/courses/{self.course.id}/assignments/{assignment.id}/')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data['user_best_score'], 30.0)

    @staticmethod
    def rows(resp):
        return resp.data['results'] if isinstance(resp.data, dict) else resp.data

    def test_instructor_filters_by_course_and_student(self):
        self.client.force_authenticate(self.instructor)
        resp = self.client.get('/api/results/', {'course': str(self.course.id),
                                                 'student': str(self.student.id)})
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual([r['id'] for r in self.rows(resp)], [str(self.result.id)])

        resp = self.client.get('/api/results/', {'lesson': str(self.lesson.id)})
        self.assertEqual({r['id'] for r in self.rows(resp)},
                         {str(self.result.id), str(self.other_result.id)})

    def test_course_and_student_results_follow_the_course_order(self):
        from datetime import timedelta
        from django.utils import timezone

        self.lesson.order = 1
        self.lesson.save(update_fields=['order'])
        self.exercise.order = 1
        self.exercise.save(update_fields=['order'])
        later = Lesson.objects.create(course=self.course, module=self.lesson.module, title='Пізніше',
                                      lesson_type='practice', is_published=True, order=2)
        later_exercise = LessonExercise.objects.create(lesson=later, title='В3',
                                                       expected_query='SELECT 1', order=1)
        second = LessonExercise.objects.create(lesson=self.lesson, title='В2',
                                               expected_query='SELECT 1', order=2)
        assignment = Assignment.objects.create(course=self.course, title='Завдання', description='d',
                                               expected_query='SELECT 1', is_published=True)
        now = timezone.now()
        made = {}
        # Created and attempted in an order unlike the course's own.
        for key, kwargs, minutes in (
            ('assignment', {'assignment': assignment}, 1),
            ('later', {'lesson': later, 'exercise': later_exercise}, 2),
            ('second', {'lesson': self.lesson, 'exercise': second}, 3),
        ):
            made[key] = UserResult.objects.create(
                student=self.student, last_attempt_at=now - timedelta(minutes=minutes), **kwargs)
        UserResult.objects.filter(pk=self.result.pk).update(last_attempt_at=now - timedelta(minutes=4))

        self.client.force_authenticate(self.instructor)
        resp = self.client.get('/api/results/', {'course': str(self.course.id),
                                                 'student': str(self.student.id)})
        self.assertEqual([r['id'] for r in self.rows(resp)], [
            str(self.result.id), str(made['second'].id), str(made['later'].id),
            str(made['assignment'].id)])

        # Without both filters the most recent attempt still comes first.
        resp = self.client.get('/api/results/', {'student': str(self.student.id)})
        self.assertEqual([r['id'] for r in self.rows(resp)], [
            str(made['assignment'].id), str(made['later'].id), str(made['second'].id),
            str(self.result.id)])

    def test_student_sees_only_their_own_results(self):
        self.client.force_authenticate(self.student)
        resp = self.client.get('/api/results/', {'student': str(self.other_student.id)})
        self.assertEqual([r['id'] for r in self.rows(resp)], [str(self.result.id)])

    def test_invalid_filter_is_a_bad_request(self):
        self.client.force_authenticate(self.instructor)
        resp = self.client.get('/api/results/', {'student': 'nope'})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
