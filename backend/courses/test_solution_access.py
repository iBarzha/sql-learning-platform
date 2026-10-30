"""Reference answers and hidden datasets are visible to the course owner and admins only."""

from rest_framework.test import APITestCase

from courses.models import Course, Dataset, Enrollment, Lesson, LessonExercise, Module
from users.models import User

SCHEMA = 'CREATE TABLE t (a INTEGER);'


class SolutionAccessTests(APITestCase):
    def setUp(self):
        self.owner = User.objects.create_user(email='owner@test.com', password='x',
                                              role=User.Role.INSTRUCTOR)
        self.other = User.objects.create_user(email='other@test.com', password='x',
                                              role=User.Role.INSTRUCTOR)
        self.admin = User.objects.create_user(email='admin@test.com', password='x',
                                              role=User.Role.ADMIN)
        self.student = User.objects.create_user(email='s@test.com', password='x',
                                                role=User.Role.STUDENT)
        self.course = Course.objects.create(title='C', instructor=self.owner,
                                            database_type='sqlite', is_published=True)
        Enrollment.objects.create(student=self.student, course=self.course)
        module = Module.objects.create(course=self.course, title='M', is_published=True)
        dataset = Dataset.objects.create(name='D', course=self.course, created_by=self.owner,
                                         database_type='sqlite', schema_sql=SCHEMA,
                                         seed_sql='INSERT INTO t VALUES (1);')
        self.lesson = Lesson.objects.create(course=self.course, module=module, title='L',
                                            lesson_type='practice', is_published=True)
        self.draft = Lesson.objects.create(course=self.course, module=module, title='Draft',
                                           lesson_type='practice', is_published=False)
        for lesson in (self.lesson, self.draft):
            LessonExercise.objects.create(
                lesson=lesson, title='E', dataset=dataset, expected_query='SELECT a FROM t',
                check_datasets=[{'name': 'секрет', 'seed_sql': 'INSERT INTO t VALUES (2);',
                                 'schema_sql': '', 'targets': 'х'}],
                criteria={'enabled': ['execution', 'complete'], 'threshold': 1})

    def detail(self, user, lesson):
        self.client.force_authenticate(user)
        return self.client.get(f'/api/courses/{self.course.id}/lessons/{lesson.id}/')

    def test_owner_sees_the_solution(self):
        resp = self.detail(self.owner, self.lesson)
        exercise = resp.data['exercises'][0]
        self.assertEqual(exercise['expected_query'], 'SELECT a FROM t')
        self.assertIn('check_datasets', exercise)
        self.assertIn('criteria', exercise)

    def test_admin_sees_the_solution(self):
        exercise = self.detail(self.admin, self.lesson).data['exercises'][0]
        self.assertEqual(exercise['expected_query'], 'SELECT a FROM t')

    def test_another_instructor_does_not_see_the_solution(self):
        resp = self.detail(self.other, self.lesson)
        self.assertEqual(resp.status_code, 200)
        exercise = resp.data['exercises'][0]
        for field in ('expected_query', 'expected_result', 'check_datasets', 'criteria'):
            self.assertNotIn(field, exercise)
        self.assertIn('criteria_summary', exercise)

    def test_another_instructor_does_not_see_drafts(self):
        self.assertEqual(self.detail(self.other, self.draft).status_code, 404)
        self.client.force_authenticate(self.other)
        resp = self.client.get(f'/api/courses/{self.course.id}/lessons/')
        titles = [item['title'] for item in (resp.data['results']
                                             if isinstance(resp.data, dict) else resp.data)]
        self.assertEqual(titles, ['L'])

    def test_student_does_not_see_the_solution(self):
        exercise = self.detail(self.student, self.lesson).data['exercises'][0]
        self.assertNotIn('expected_query', exercise)
        self.assertNotIn('criteria', exercise)

    def test_validate_exercises_is_owner_only(self):
        self.client.force_authenticate(self.other)
        resp = self.client.post(
            f'/api/courses/{self.course.id}/lessons/{self.lesson.id}/validate-exercises/')
        self.assertEqual(resp.status_code, 403)
        self.client.force_authenticate(self.owner)
        resp = self.client.post(
            f'/api/courses/{self.course.id}/lessons/{self.lesson.id}/validate-exercises/')
        self.assertEqual(resp.status_code, 200, resp.data)
