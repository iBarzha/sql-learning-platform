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
