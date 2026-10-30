"""Instructor-configured grading criteria through the REST API."""

from rest_framework.test import APITestCase

from assignments.models import Assignment
from courses.models import Course, Enrollment, Lesson, Module
from users.models import User

SCHEMA = 'CREATE TABLE t (a INTEGER, b TEXT);'
SEED = "INSERT INTO t VALUES (1,'x'),(2,'y');"


class CriteriaApiBase(APITestCase):
    """Course with a SQLite dataset; the instructor is logged in."""

    def setUp(self):
        self.instructor = User.objects.create_user(email='i@test.com', password='x',
                                                   role=User.Role.INSTRUCTOR)
        self.student = User.objects.create_user(email='s@test.com', password='x',
                                                role=User.Role.STUDENT)
        self.course = Course.objects.create(title='C', instructor=self.instructor,
                                            database_type='sqlite', is_published=True)
        Enrollment.objects.create(student=self.student, course=self.course)
        self.module = Module.objects.create(course=self.course, title='M', is_published=True)
        self.client.force_authenticate(self.instructor)
        resp = self.client.post(f'/api/courses/{self.course.id}/datasets/', {
            'name': 'D', 'database_type': 'sqlite', 'schema_sql': SCHEMA, 'seed_sql': SEED,
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        self.dataset_id = resp.data['id']

    def lesson_payload(self, exercise):
        return {'title': 'L', 'lesson_type': 'practice', 'module_id': str(self.module.id),
                'is_published': True,
                'exercises': [dict(title='E', dataset_id=self.dataset_id, **exercise)]}

    def create_lesson(self, exercise):
        return self.client.post(f'/api/courses/{self.course.id}/lessons/',
                                self.lesson_payload(exercise), format='json')

    def lesson_detail(self, lesson, as_user=None):
        if as_user is not None:
            self.client.force_authenticate(as_user)
        return self.client.get(f'/api/courses/{self.course.id}/lessons/{lesson.id}/')


class CriteriaApiTests(CriteriaApiBase):
    def test_catalog_lists_general_criteria(self):
        resp = self.client.get('/api/grading/criteria/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data[0]['id'], 'execution')
        self.assertEqual(len(resp.data), 8)

    def test_catalog_requires_login(self):
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get('/api/grading/criteria/').status_code, 401)

    def test_criteria_are_saved_normalized(self):
        resp = self.create_lesson({'expected_query': 'SELECT a FROM t ORDER BY a',
                                   'criteria': {'enabled': ['precise', 'order'], 'threshold': 2}})
        self.assertEqual(resp.status_code, 201, resp.data)
        exercise = Lesson.objects.get(title='L').exercises.first()
        self.assertEqual(exercise.criteria, {'enabled': ['execution', 'precise', 'order'],
                                             'threshold': 2})

    def test_criteria_survive_an_update(self):
        self.create_lesson({'expected_query': 'SELECT a FROM t',
                            'criteria': {'enabled': ['complete'], 'threshold': 1}})
        lesson = Lesson.objects.get(title='L')
        exercise = lesson.exercises.first()
        resp = self.client.patch(f'/api/courses/{self.course.id}/lessons/{lesson.id}/', {
            'exercises': [{'id': str(exercise.id), 'title': 'E', 'dataset_id': self.dataset_id,
                           'expected_query': 'SELECT a FROM t',
                           'criteria': {'enabled': ['precise'], 'threshold': 2}}],
        }, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        exercise.refresh_from_db()
        self.assertEqual(exercise.criteria, {'enabled': ['execution', 'precise'], 'threshold': 2})

    def test_unknown_criterion_is_rejected(self):
        resp = self.create_lesson({'expected_query': 'SELECT a FROM t',
                                   'criteria': {'enabled': ['magic']}})
        self.assertEqual(resp.status_code, 400)
        self.assertIn('Невідомий критерій', str(resp.data))

    def test_order_without_order_by_is_rejected(self):
        resp = self.create_lesson({'expected_query': 'SELECT a FROM t',
                                   'criteria': {'enabled': ['order']}})
        self.assertEqual(resp.status_code, 400)
        self.assertIn('ORDER BY', str(resp.data))

    def test_negative_threshold_is_rejected(self):
        resp = self.create_lesson({'expected_query': 'SELECT a FROM t',
                                   'criteria': {'threshold': -1}})
        self.assertEqual(resp.status_code, 400)

    def test_student_gets_summary_but_not_config(self):
        self.create_lesson({'expected_query': 'SELECT a FROM t ORDER BY a',
                            'required_keywords': ['ORDER BY'],
                            'criteria': {'enabled': ['complete', 'precise'], 'threshold': 3}})
        lesson = Lesson.objects.get(title='L')
        resp = self.lesson_detail(lesson, as_user=self.student)
        exercise = resp.data['exercises'][0]
        self.assertNotIn('criteria', exercise)
        self.assertNotIn('expected_query', exercise)
        self.assertEqual(exercise['criteria_summary'], {
            'criteria': [{'id': 'execution', 'name': 'Запит виконується'},
                         {'id': 'complete', 'name': 'Усі потрібні рядки є'},
                         {'id': 'precise', 'name': 'Немає зайвих рядків'},
                         {'id': 'require:ORDER BY', 'name': 'Використано ORDER BY'}],
            'total': 4, 'threshold': 3})

    def test_default_summary_for_an_unconfigured_exercise(self):
        self.create_lesson({'expected_query': 'SELECT a FROM t'})
        lesson = Lesson.objects.get(title='L')
        resp = self.lesson_detail(lesson, as_user=self.student)
        summary = resp.data['exercises'][0]['criteria_summary']
        self.assertEqual([c['id'] for c in summary['criteria']],
                         ['execution', 'columns', 'complete', 'precise', 'reads_data'])
        self.assertEqual(summary['threshold'], 5)

    def test_instructor_sees_both(self):
        self.create_lesson({'expected_query': 'SELECT a FROM t',
                            'criteria': {'enabled': ['complete'], 'threshold': 1}})
        lesson = Lesson.objects.get(title='L')
        resp = self.lesson_detail(lesson)
        exercise = resp.data['exercises'][0]
        self.assertEqual(exercise['criteria'], {'enabled': ['execution', 'complete'],
                                                'threshold': 1})
        self.assertIn('criteria_summary', exercise)

    def test_assignment_criteria_round_trip(self):
        resp = self.client.post(f'/api/courses/{self.course.id}/assignments/', {
            'title': 'A', 'description': 'd', 'query_type': 'select', 'difficulty': 'easy',
            'dataset': self.dataset_id, 'expected_query': 'SELECT a FROM t',
            'is_published': True,
            'criteria': {'enabled': ['columns'], 'threshold': 9},
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        assignment_id = Assignment.objects.get(title='A').id
        self.client.force_authenticate(self.student)
        detail = self.client.get(f'/api/courses/{self.course.id}/assignments/{assignment_id}/')
        self.assertEqual(detail.status_code, 200, detail.data)
        self.assertNotIn('criteria', detail.data)
        self.assertEqual(detail.data['criteria_summary']['threshold'], 2)   # clamped to total

    def test_form_payload_with_empty_enabled_keeps_the_defaults(self):
        # What the lesson form sends for an exercise whose criteria were never touched.
        resp = self.create_lesson({'expected_query': 'SELECT a FROM t',
                                   'criteria': {'enabled': [], 'threshold': 0}})
        self.assertEqual(resp.status_code, 201, resp.data)
        lesson = Lesson.objects.get(title='L')
        self.assertEqual(lesson.exercises.first().criteria, {})
        resp = self.lesson_detail(lesson, as_user=self.student)
        summary = resp.data['exercises'][0]['criteria_summary']
        self.assertEqual([c['id'] for c in summary['criteria']],
                         ['execution', 'columns', 'complete', 'precise', 'reads_data'])

    def test_assignment_patch_without_criteria_drops_stale_ids(self):
        resp = self.client.post(f'/api/courses/{self.course.id}/assignments/', {
            'title': 'A', 'description': 'd', 'query_type': 'select', 'difficulty': 'easy',
            'dataset': self.dataset_id, 'expected_query': 'SELECT a FROM t ORDER BY a',
            'is_published': True, 'criteria': {'enabled': ['order', 'precise'], 'threshold': 2},
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        assignment = Assignment.objects.get(title='A')
        resp = self.client.patch(
            f'/api/courses/{self.course.id}/assignments/{assignment.id}/',
            {'expected_query': 'SELECT a FROM t'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        assignment.refresh_from_db()
        self.assertEqual(assignment.criteria, {'enabled': ['execution', 'precise'], 'threshold': 2})

    def test_assignment_criteria_are_validated(self):
        resp = self.client.post(f'/api/courses/{self.course.id}/assignments/', {
            'title': 'A', 'description': 'd', 'query_type': 'select', 'difficulty': 'easy',
            'dataset': self.dataset_id, 'expected_query': 'SELECT a FROM t',
            'criteria': {'enabled': ['order']},
        }, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertIn('ORDER BY', str(resp.data))


REFERENCE_REQUIRED = 'Потрібен еталонний запит: без нього відповідь не перевіряється.'
LEGACY_RESULT = {'columns': ['a'], 'rows': [[1], [2]]}


class ReferenceRequiredTests(CriteriaApiBase):
    def create_assignment(self, **fields):
        payload = {'title': 'A', 'description': 'd', 'query_type': 'select',
                   'difficulty': 'easy', 'dataset': self.dataset_id, 'is_published': True}
        payload.update(fields)
        return self.client.post(f'/api/courses/{self.course.id}/assignments/', payload,
                                format='json')

    def test_exercise_without_reference_is_rejected(self):
        for blank in ('', '   '):
            resp = self.create_lesson({'expected_query': blank})
            self.assertEqual(resp.status_code, 400, resp.data)
            self.assertEqual(resp.data, {'exercises': [{'expected_query': [REFERENCE_REQUIRED]}]})
        self.assertFalse(Lesson.objects.filter(title='L').exists())

    def test_exercise_with_a_legacy_expected_result_is_accepted(self):
        resp = self.create_lesson({'expected_query': '', 'expected_result': LEGACY_RESULT})
        self.assertEqual(resp.status_code, 201, resp.data)

    def test_lesson_patch_with_an_emptied_reference_is_rejected(self):
        self.assertEqual(self.create_lesson({'expected_query': 'SELECT a FROM t'}).status_code, 201)
        lesson = Lesson.objects.get(title='L')
        exercise = lesson.exercises.first()
        resp = self.client.patch(f'/api/courses/{self.course.id}/lessons/{lesson.id}/', {
            'exercises': [{'id': str(exercise.id), 'title': 'E', 'expected_query': ''}],
        }, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.data['exercises'][0]['expected_query'], [REFERENCE_REQUIRED])
        # A patch that does not resend exercises is not affected.
        resp = self.client.patch(f'/api/courses/{self.course.id}/lessons/{lesson.id}/',
                                 {'title': 'L2'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)

    def test_assignment_without_reference_is_rejected(self):
        resp = self.create_assignment(expected_query='  ')
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.data, {'expected_query': [REFERENCE_REQUIRED]})

    def test_assignment_with_a_legacy_expected_result_is_accepted(self):
        resp = self.create_assignment(expected_query='', expected_result=LEGACY_RESULT)
        self.assertEqual(resp.status_code, 201, resp.data)

    def test_assignment_patch_without_the_reference_is_not_affected(self):
        self.assertEqual(self.create_assignment(expected_query='SELECT a FROM t').status_code, 201)
        assignment = Assignment.objects.get(title='A')
        url = f'/api/courses/{self.course.id}/assignments/{assignment.id}/'
        self.assertEqual(self.client.patch(url, {'title': 'B'}, format='json').status_code, 200)
        resp = self.client.patch(url, {'expected_query': ''}, format='json')
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.data, {'expected_query': [REFERENCE_REQUIRED]})


class IgnoreColumnOrderTests(CriteriaApiBase):
    def test_exercise_flag_round_trips_through_the_lesson_api(self):
        resp = self.create_lesson({'expected_query': 'SELECT a, b FROM t'})
        self.assertEqual(resp.status_code, 201, resp.data)
        lesson = Lesson.objects.get(title='L')
        exercise = lesson.exercises.first()
        self.assertFalse(exercise.ignore_column_order)          # off by default
        resp = self.client.patch(f'/api/courses/{self.course.id}/lessons/{lesson.id}/', {
            'exercises': [{'id': str(exercise.id), 'title': 'E', 'dataset_id': self.dataset_id,
                           'expected_query': 'SELECT a, b FROM t', 'ignore_column_order': True}],
        }, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        exercise.refresh_from_db()
        self.assertTrue(exercise.ignore_column_order)
        self.assertTrue(self.lesson_detail(lesson).data['exercises'][0]['ignore_column_order'])

    def test_assignment_flag_round_trips(self):
        resp = self.client.post(f'/api/courses/{self.course.id}/assignments/', {
            'title': 'A', 'description': 'd', 'query_type': 'select', 'difficulty': 'easy',
            'dataset': self.dataset_id, 'expected_query': 'SELECT a, b FROM t',
            'is_published': True, 'ignore_column_order': True,
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        assignment = Assignment.objects.get(title='A')
        self.assertTrue(assignment.ignore_column_order)
        detail = self.client.get(f'/api/courses/{self.course.id}/assignments/{assignment.id}/')
        self.assertTrue(detail.data['ignore_column_order'])
        resp = self.client.patch(f'/api/courses/{self.course.id}/assignments/{assignment.id}/',
                                 {'ignore_column_order': False}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        assignment.refresh_from_db()
        self.assertFalse(assignment.ignore_column_order)

    def test_duplication_keeps_criteria_and_the_flag(self):
        criteria = {'enabled': ['complete'], 'threshold': 1}
        resp = self.create_lesson({'expected_query': 'SELECT a, b FROM t',
                                   'ignore_column_order': True, 'criteria': criteria})
        self.assertEqual(resp.status_code, 201, resp.data)
        resp = self.client.post(f'/api/courses/{self.course.id}/assignments/', {
            'title': 'A', 'description': 'd', 'query_type': 'select', 'difficulty': 'easy',
            'dataset': self.dataset_id, 'expected_query': 'SELECT a, b FROM t',
            'ignore_column_order': True, 'criteria': criteria,
        }, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)

        resp = self.client.post(f'/api/courses/{self.course.id}/duplicate/', {}, format='json')
        self.assertEqual(resp.status_code, 201, resp.data)
        copy_id = resp.data['id']
        exercise = Lesson.objects.get(course_id=copy_id).exercises.get()
        assignment = Assignment.objects.get(course_id=copy_id)
        normalized = {'enabled': ['execution', 'complete'], 'threshold': 1}
        self.assertEqual(exercise.criteria, normalized)
        self.assertTrue(exercise.ignore_column_order)
        self.assertEqual(assignment.criteria, normalized)
        self.assertTrue(assignment.ignore_column_order)
