"""Enrollment lifecycle, course duplication and admin visibility through the API."""

from rest_framework import status
from rest_framework.test import APITestCase

from courses.models import Course, Dataset, Enrollment, Lesson, LessonExercise, Module
from users.models import User


class EnrollmentLifecycleTests(APITestCase):
    def setUp(self):
        self.instructor = User.objects.create_user(
            email='t@test.com', password='x', role=User.Role.INSTRUCTOR, first_name='T', last_name='T')
        self.student = User.objects.create_user(
            email='s@test.com', password='x', role=User.Role.STUDENT, first_name='S', last_name='S')
        self.course = Course.objects.create(title='C', instructor=self.instructor,
                                            database_type='sqlite', is_published=True)
        self.client.force_authenticate(self.student)

    def join(self):
        return self.client.post('/api/courses/join/', {'code': self.course.course_code}, format='json')

    def test_dropped_student_can_rejoin_by_code(self):
        self.assertEqual(self.join().status_code, status.HTTP_201_CREATED)
        self.assertEqual(self.client.post(f'/api/courses/{self.course.id}/unenroll/').status_code, 200)
        self.assertEqual(Enrollment.objects.get(student=self.student).status, 'dropped')

        resp = self.join()
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        enrollment = Enrollment.objects.get(student=self.student, course=self.course)
        self.assertEqual(enrollment.status, 'active')
        self.assertEqual(Enrollment.objects.filter(student=self.student).count(), 1)

    def test_dropped_student_can_re_enroll(self):
        self.join()
        self.client.post(f'/api/courses/{self.course.id}/unenroll/')
        resp = self.client.post(f'/api/courses/{self.course.id}/enroll/')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        self.assertEqual(Enrollment.objects.get(student=self.student).status, 'active')

    def test_active_student_cannot_enroll_twice(self):
        self.join()
        resp = self.client.post(f'/api/courses/{self.course.id}/enroll/')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_rejoin_respects_capacity(self):
        self.course.max_students = 1
        self.course.save()
        self.join()
        self.client.post(f'/api/courses/{self.course.id}/unenroll/')
        other = User.objects.create_user(email='o@test.com', password='x', role=User.Role.STUDENT,
                                         first_name='O', last_name='O')
        Enrollment.objects.create(student=other, course=self.course)
        resp = self.join()
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('full', resp.data['detail'].lower())


class DuplicateCourseTests(APITestCase):
    def setUp(self):
        self.instructor = User.objects.create_user(
            email='t@test.com', password='x', role=User.Role.INSTRUCTOR, first_name='T', last_name='T')
        self.client.force_authenticate(self.instructor)
        self.course = Course.objects.create(title='Оригінал', instructor=self.instructor,
                                            database_type='sqlite', is_published=True)
        self.course_dataset = Dataset.objects.create(
            name='Курсовий', course=self.course, created_by=self.instructor,
            database_type='sqlite', schema_sql='CREATE TABLE t (a INT);', seed_sql='INSERT INTO t VALUES (1);')
        self.library_dataset = Dataset.objects.create(
            name='Бібліотечний', course=None, created_by=self.instructor,
            database_type='sqlite', schema_sql='CREATE TABLE u (b INT);', seed_sql='')
        module = Module.objects.create(course=self.course, title='M', is_published=True)
        lesson = Lesson.objects.create(course=self.course, module=module, title='L',
                                       lesson_type='practice', is_published=True)
        self.hidden = [{'name': 'h', 'seed_sql': 'INSERT INTO t VALUES (2);', 'schema_sql': '', 'targets': 't'}]
        LessonExercise.objects.create(lesson=lesson, title='E1', expected_query='SELECT a FROM t',
                                      dataset=self.course_dataset, check_datasets=self.hidden)
        LessonExercise.objects.create(lesson=lesson, title='E2', expected_query='SELECT b FROM u',
                                      dataset=self.library_dataset)

    def test_duplicate_keeps_hidden_datasets_and_dataset_links(self):
        resp = self.client.post(f'/api/courses/{self.course.id}/duplicate/', {}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        copy = Course.objects.get(id=resp.data['id'])
        exercises = {e.title: e for e in LessonExercise.objects.filter(lesson__course=copy)}

        e1, e2 = exercises['E1'], exercises['E2']
        self.assertEqual(e1.check_datasets, self.hidden)
        self.assertIsNotNone(e1.dataset)
        self.assertEqual(e1.dataset.course_id, copy.id)          # course dataset was cloned
        self.assertEqual(e1.dataset.created_by_id, self.instructor.id)
        self.assertEqual(e2.dataset_id, self.library_dataset.id)  # library dataset is shared

    def test_duplicate_is_a_draft_with_a_new_code(self):
        resp = self.client.post(f'/api/courses/{self.course.id}/duplicate/', {}, format='json')
        copy = Course.objects.get(id=resp.data['id'])
        self.assertFalse(copy.is_published)
        self.assertNotEqual(copy.course_code, self.course.course_code)


class AdminCourseVisibilityTests(APITestCase):
    def test_admin_sees_every_course_in_the_list(self):
        instructor = User.objects.create_user(
            email='t@test.com', password='x', role=User.Role.INSTRUCTOR, first_name='T', last_name='T')
        admin = User.objects.create_user(
            email='a@test.com', password='x', role=User.Role.ADMIN, first_name='A', last_name='A')
        Course.objects.create(title='Чужий', instructor=instructor, database_type='sqlite')

        self.client.force_authenticate(admin)
        resp = self.client.get('/api/courses/')
        items = resp.data['results'] if isinstance(resp.data, dict) else resp.data
        self.assertEqual([c['title'] for c in items], ['Чужий'])

        self.client.force_authenticate(instructor)
        other = User.objects.create_user(
            email='t2@test.com', password='x', role=User.Role.INSTRUCTOR, first_name='T2', last_name='T')
        Course.objects.create(title='Не мій', instructor=other, database_type='sqlite')
        resp = self.client.get('/api/courses/')
        items = resp.data['results'] if isinstance(resp.data, dict) else resp.data
        self.assertEqual([c['title'] for c in items], ['Чужий'])


class GenerateDatasetStatusTests(APITestCase):
    def test_missing_api_key_is_service_unavailable(self):
        instructor = User.objects.create_user(
            email='t@test.com', password='x', role=User.Role.INSTRUCTOR, first_name='T', last_name='T')
        self.client.force_authenticate(instructor)
        with self.settings(GEMINI_API_KEY=''):
            resp = self.client.post('/api/datasets/generate/', {'topic': 'library'}, format='json')
        self.assertIn(resp.status_code, (status.HTTP_503_SERVICE_UNAVAILABLE, status.HTTP_502_BAD_GATEWAY))
        self.assertTrue(resp.data['detail'])


class DeleteCourseTests(APITestCase):
    def setUp(self):
        self.instructor = User.objects.create_user(
            email='t@test.com', password='x', role=User.Role.INSTRUCTOR, first_name='T', last_name='T')
        self.client.force_authenticate(self.instructor)
        self.course = Course.objects.create(title='Оригінал', instructor=self.instructor, database_type='sqlite')
        self.course_dataset = Dataset.objects.create(
            name='Курсовий', course=self.course, created_by=self.instructor,
            database_type='sqlite', schema_sql='CREATE TABLE t (a INT);')
        self.library_dataset = Dataset.objects.create(
            name='Бібліотечний', course=None, created_by=self.instructor,
            database_type='sqlite', schema_sql='CREATE TABLE u (b INT);')

    def library_names(self):
        data = self.client.get('/api/datasets/').data
        rows = data['results'] if isinstance(data, dict) else data
        return sorted(d['name'] for d in rows)

    def test_deleting_a_course_removes_its_datasets_but_keeps_library_ones(self):
        resp = self.client.delete(f'/api/courses/{self.course.id}/')
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Dataset.objects.filter(id=self.course_dataset.id).exists())
        self.assertTrue(Dataset.objects.filter(id=self.library_dataset.id).exists())
        self.assertEqual(self.library_names(), ['Бібліотечний'])

    def test_deleting_a_duplicate_leaves_no_orphan_in_the_library(self):
        copy_id = self.client.post(f'/api/courses/{self.course.id}/duplicate/', {}, format='json').data['id']
        self.assertEqual(Dataset.objects.filter(course_id=copy_id).count(), 1)

        resp = self.client.delete(f'/api/courses/{copy_id}/')
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(self.library_names(), ['Бібліотечний'])
        self.assertTrue(Dataset.objects.filter(id=self.course_dataset.id).exists())


class DeleteDatasetTests(APITestCase):
    def setUp(self):
        self.instructor = User.objects.create_user(
            email='t@test.com', password='x', role=User.Role.INSTRUCTOR, first_name='T', last_name='T')
        self.client.force_authenticate(self.instructor)
        self.course = Course.objects.create(title='Курс', instructor=self.instructor, database_type='sqlite')
        self.used = Dataset.objects.create(
            name='Уживаний', course=None, created_by=self.instructor,
            database_type='sqlite', schema_sql='CREATE TABLE t (a INT);')
        self.unused = Dataset.objects.create(
            name='Вільний', course=None, created_by=self.instructor,
            database_type='sqlite', schema_sql='CREATE TABLE u (b INT);')
        self.course_dataset = Dataset.objects.create(
            name='Курсовий', course=self.course, created_by=self.instructor,
            database_type='sqlite', schema_sql='CREATE TABLE v (c INT);')
        module = Module.objects.create(course=self.course, title='Модуль', is_published=True)
        lesson = Lesson.objects.create(course=self.course, module=module, title='Урок', lesson_type='practice',
                                       is_published=True)
        LessonExercise.objects.create(lesson=lesson, title='Вправа', expected_query='SELECT a FROM t',
                                      dataset=self.used)
        LessonExercise.objects.create(lesson=lesson, title='Ще вправа', expected_query='SELECT c FROM v',
                                      dataset=self.course_dataset)

    def test_dataset_used_by_an_exercise_is_not_deleted(self):
        resp = self.client.delete(f'/api/datasets/{self.used.id}/')
        self.assertEqual(resp.status_code, status.HTTP_409_CONFLICT, resp.data)
        self.assertEqual(resp.data['code'], 'dataset_in_use')
        self.assertEqual(resp.data['count'], 1)
        self.assertEqual(resp.data['exercises'], [{'course': 'Курс', 'lesson': 'Урок', 'title': 'Вправа'}])
        self.assertTrue(Dataset.objects.filter(id=self.used.id).exists())

    def test_unused_dataset_is_deleted(self):
        resp = self.client.delete(f'/api/datasets/{self.unused.id}/')
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Dataset.objects.filter(id=self.unused.id).exists())

    def test_course_dataset_used_by_an_exercise_is_not_deleted(self):
        resp = self.client.delete(f'/api/courses/{self.course.id}/datasets/{self.course_dataset.id}/')
        self.assertEqual(resp.status_code, status.HTTP_409_CONFLICT, resp.data)
        self.assertTrue(Dataset.objects.filter(id=self.course_dataset.id).exists())

    def test_dataset_is_deletable_once_the_exercise_moved_on(self):
        LessonExercise.objects.filter(dataset=self.used).update(dataset=self.unused)
        resp = self.client.delete(f'/api/datasets/{self.used.id}/')
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)


class SystemDatasetPermissionTests(APITestCase):
    def setUp(self):
        self.instructor = User.objects.create_user(
            email='t@test.com', password='x', role=User.Role.INSTRUCTOR, first_name='T', last_name='T')
        self.admin = User.objects.create_user(
            email='a@test.com', password='x', role=User.Role.ADMIN, first_name='A', last_name='A')
        self.system = Dataset.objects.create(
            name='Системний', course=None, created_by=None,
            database_type='sqlite', schema_sql='CREATE TABLE s (a INT);')

    def test_instructor_cannot_edit_or_delete_a_system_dataset(self):
        self.client.force_authenticate(self.instructor)
        resp = self.client.patch(f'/api/datasets/{self.system.id}/', {'name': 'Мій'}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        resp = self.client.delete(f'/api/datasets/{self.system.id}/')
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(Dataset.objects.filter(id=self.system.id).exists())

    def test_admin_can_edit_and_delete_a_system_dataset(self):
        self.client.force_authenticate(self.admin)
        resp = self.client.patch(f'/api/datasets/{self.system.id}/', {'name': 'Оновлений'}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        resp = self.client.delete(f'/api/datasets/{self.system.id}/')
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)


class CrossCourseDatasetTests(APITestCase):
    def setUp(self):
        self.instructor = User.objects.create_user(
            email='t@test.com', password='x', role=User.Role.INSTRUCTOR, first_name='T', last_name='T')
        self.client.force_authenticate(self.instructor)
        self.course = Course.objects.create(title='A', instructor=self.instructor, database_type='sqlite')
        self.other = Course.objects.create(title='B', instructor=self.instructor, database_type='sqlite')
        self.other_dataset = Dataset.objects.create(
            name='Набір курсу B', course=self.other, created_by=self.instructor,
            database_type='sqlite', schema_sql='CREATE TABLE t (a INT);')
        self.library_dataset = Dataset.objects.create(
            name='Бібліотечний', course=None, created_by=self.instructor,
            database_type='sqlite', schema_sql='CREATE TABLE t (a INT);')
        self.module = Module.objects.create(course=self.course, title='M', is_published=True)
        self.lesson = Lesson.objects.create(course=self.course, module=self.module, title='L',
                                            lesson_type='practice', is_published=True)

    def patch_lesson(self, dataset_id):
        return self.client.patch(
            f'/api/courses/{self.course.id}/lessons/{self.lesson.id}/',
            {'exercises': [{'title': 'E', 'expected_query': 'SELECT a FROM t', 'dataset_id': str(dataset_id)}]},
            format='json')

    def test_exercise_may_use_a_library_dataset_but_not_another_courses(self):
        self.assertEqual(self.patch_lesson(self.library_dataset.id).status_code, status.HTTP_200_OK)
        resp = self.patch_lesson(self.other_dataset.id)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST, resp.data)
        self.assertIn('exercises', resp.data)
        self.assertEqual(LessonExercise.objects.get(lesson=self.lesson).dataset_id, self.library_dataset.id)

    def test_new_lesson_cannot_use_another_courses_dataset(self):
        resp = self.client.post(
            f'/api/courses/{self.course.id}/lessons/',
            {'title': 'L2', 'lesson_type': 'practice', 'module_id': str(self.module.id),
             'exercises': [{'title': 'E', 'expected_query': 'SELECT a FROM t', 'dataset_id': str(self.other_dataset.id)}]},
            format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST, resp.data)

    def test_assignment_cannot_use_another_courses_dataset(self):
        payload = {'title': 'Завдання', 'description': 'опис', 'expected_query': 'SELECT a FROM t',
                   'dataset': str(self.library_dataset.id)}
        resp = self.client.post(f'/api/courses/{self.course.id}/assignments/', payload, format='json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        payload['dataset'] = str(self.other_dataset.id)
        resp = self.client.post(f'/api/courses/{self.course.id}/assignments/', payload, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST, resp.data)
        self.assertIn('dataset', resp.data)

    def test_course_whose_dataset_is_used_elsewhere_is_not_deleted(self):
        LessonExercise.objects.create(lesson=self.lesson, title='E', expected_query='SELECT a FROM t',
                                      dataset=self.other_dataset)   # legacy cross-course link
        resp = self.client.delete(f'/api/courses/{self.other.id}/')
        self.assertEqual(resp.status_code, status.HTTP_409_CONFLICT, resp.data)
        self.assertEqual(resp.data['code'], 'datasets_in_use_elsewhere')
        self.assertTrue(Course.objects.filter(id=self.other.id).exists())
        self.assertTrue(Dataset.objects.filter(id=self.other_dataset.id).exists())


class LibraryDatasetVisibilityTests(APITestCase):
    def setUp(self):
        self.instructor = User.objects.create_user(
            email='t@test.com', password='x', role=User.Role.INSTRUCTOR, first_name='T', last_name='T')
        self.stranger = User.objects.create_user(
            email='u@test.com', password='x', role=User.Role.INSTRUCTOR, first_name='U', last_name='U')
        self.admin = User.objects.create_user(
            email='a@test.com', password='x', role=User.Role.ADMIN, first_name='A', last_name='A')
        self.course = Course.objects.create(title='A', instructor=self.instructor, database_type='sqlite')
        module = Module.objects.create(course=self.course, title='M', is_published=True)
        self.lesson = Lesson.objects.create(course=self.course, module=module, title='L',
                                            lesson_type='practice', is_published=True)
        mk = lambda name, author: Dataset.objects.create(
            name=name, course=None, created_by=author, database_type='sqlite', schema_sql='CREATE TABLE t (a INT);')
        self.system = mk('Системний', None)
        self.own = mk('Власний', self.instructor)
        self.private = mk('Чужий', self.stranger)

    def patch_lesson(self, dataset_id, user=None):
        self.client.force_authenticate(user or self.instructor)
        return self.client.patch(
            f'/api/courses/{self.course.id}/lessons/{self.lesson.id}/',
            {'exercises': [{'title': 'E', 'expected_query': 'SELECT a FROM t', 'dataset_id': str(dataset_id)}]},
            format='json')

    def test_system_and_own_library_datasets_are_accepted(self):
        self.assertEqual(self.patch_lesson(self.system.id).status_code, status.HTTP_200_OK)
        self.assertEqual(self.patch_lesson(self.own.id).status_code, status.HTTP_200_OK)

    def test_another_instructors_library_dataset_is_refused(self):
        resp = self.patch_lesson(self.private.id)
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST, resp.data)
        self.assertFalse(LessonExercise.objects.filter(dataset=self.private).exists())

    def test_unknown_dataset_id_is_refused(self):
        import uuid
        resp = self.patch_lesson(uuid.uuid4())
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST, resp.data)

    def test_admin_may_attach_the_course_instructors_dataset(self):
        self.assertEqual(self.patch_lesson(self.own.id, user=self.admin).status_code, status.HTTP_200_OK)
        self.assertEqual(self.patch_lesson(self.private.id, user=self.admin).status_code, status.HTTP_200_OK)

    def test_assignment_follows_the_same_rule(self):
        self.client.force_authenticate(self.instructor)
        payload = {'title': 'Завдання', 'description': 'опис', 'expected_query': 'SELECT a FROM t',
                   'dataset': str(self.private.id)}
        resp = self.client.post(f'/api/courses/{self.course.id}/assignments/', payload, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST, resp.data)
        payload['dataset'] = str(self.system.id)
        resp = self.client.post(f'/api/courses/{self.course.id}/assignments/', payload, format='json')
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
