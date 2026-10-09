"""Admin actions over users: role/active changes, password reset, deletion."""

from rest_framework import status
from rest_framework.test import APITestCase

from courses.models import Course
from users.models import User


class AdminUserActionsTestCase(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            email='admin@test.com', password='x', role=User.Role.ADMIN,
            first_name='Адмін', last_name='Тестовий')
        self.student = User.objects.create_user(
            email='student@test.com', password='x', role=User.Role.STUDENT)
        self.instructor = User.objects.create_user(
            email='teacher@test.com', password='x', role=User.Role.INSTRUCTOR)
        self.client.force_authenticate(self.admin)

    def url(self, user, suffix=''):
        return f'/api/auth/admin/users/{user.id}/{suffix}'

    # ── role / active ───────────────────────────────────────────────────

    def test_change_role(self):
        resp = self.client.patch(self.url(self.student), {'role': 'instructor'}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        self.assertEqual(resp.data['role'], 'instructor')
        self.student.refresh_from_db()
        self.assertEqual(self.student.role, 'instructor')

    def test_deactivate_and_reactivate(self):
        resp = self.client.patch(self.url(self.student), {'is_active': False}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertFalse(resp.data['is_active'])
        resp = self.client.patch(self.url(self.student), {'is_active': True}, format='json')
        self.assertTrue(resp.data['is_active'])

    def test_deactivated_user_cannot_log_in(self):
        self.client.patch(self.url(self.student), {'is_active': False}, format='json')
        self.client.force_authenticate(None)
        resp = self.client.post('/api/auth/login/',
                                {'email': 'student@test.com', 'password': 'x'}, format='json')
        self.assertIn(resp.status_code, (400, 401, 403))

    def test_empty_patch_is_rejected(self):
        resp = self.client.patch(self.url(self.student), {}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_invalid_role_is_rejected(self):
        resp = self.client.patch(self.url(self.student), {'role': 'king'}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_admin_cannot_demote_self(self):
        resp = self.client.patch(self.url(self.admin), {'role': 'student'}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.admin.refresh_from_db()
        self.assertEqual(self.admin.role, 'admin')

    def test_admin_cannot_deactivate_self(self):
        resp = self.client.patch(self.url(self.admin), {'is_active': False}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.is_active)

    def test_unknown_user_is_404(self):
        resp = self.client.patch('/api/auth/admin/users/00000000-0000-0000-0000-000000000000/',
                                 {'role': 'student'}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    # ── reset password ──────────────────────────────────────────────────

    def test_reset_password_returns_temporary_password(self):
        resp = self.client.post(self.url(self.student, 'reset-password/'))
        self.assertEqual(resp.status_code, status.HTTP_200_OK, resp.data)
        password = resp.data['temporary_password']
        self.assertEqual(len(password), 10)
        self.student.refresh_from_db()
        self.assertTrue(self.student.must_change_password)
        self.assertTrue(self.student.check_password(password))
        self.assertFalse(self.student.check_password('x'))

    # ── delete ──────────────────────────────────────────────────────────

    def test_delete_student(self):
        resp = self.client.delete(self.url(self.student))
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(User.objects.filter(id=self.student.id).exists())

    def test_delete_instructor_with_courses_is_refused(self):
        Course.objects.create(title='Бази даних', instructor=self.instructor)
        resp = self.client.delete(self.url(self.instructor))
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp.data['courses'], ['Бази даних'])
        self.assertTrue(User.objects.filter(id=self.instructor.id).exists())

    def test_delete_instructor_without_courses(self):
        resp = self.client.delete(self.url(self.instructor))
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)

    def test_admin_cannot_delete_self(self):
        resp = self.client.delete(self.url(self.admin))
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertTrue(User.objects.filter(id=self.admin.id).exists())

    # ── permissions ─────────────────────────────────────────────────────

    def test_non_admin_is_forbidden(self):
        self.client.force_authenticate(self.instructor)
        self.assertEqual(
            self.client.patch(self.url(self.student), {'role': 'admin'}, format='json').status_code,
            status.HTTP_403_FORBIDDEN)
        self.assertEqual(
            self.client.post(self.url(self.student, 'reset-password/')).status_code,
            status.HTTP_403_FORBIDDEN)
        self.assertEqual(
            self.client.delete(self.url(self.student)).status_code,
            status.HTTP_403_FORBIDDEN)

    def test_anonymous_is_rejected(self):
        self.client.force_authenticate(None)
        resp = self.client.delete(self.url(self.student))
        self.assertIn(resp.status_code, (401, 403))

    # ── list ────────────────────────────────────────────────────────────

    def test_list_exposes_last_login_and_is_active(self):
        resp = self.client.get('/api/auth/admin/users/')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        row = resp.data['results'][0]
        self.assertIn('last_login', row)
        self.assertIn('is_active', row)


class PrivilegeRevocationTests(APITestCase):
    """Role and password changes must take effect for sessions that already exist."""

    def setUp(self):
        self.admin = User.objects.create_user(
            email='admin@test.com', password='x', role=User.Role.ADMIN,
            is_staff=True, is_superuser=True)
        self.second = User.objects.create_user(
            email='second@test.com', password='x', role=User.Role.ADMIN,
            is_staff=True, is_superuser=True)
        self.student = User.objects.create_user(
            email='student@test.com', password='x', role=User.Role.STUDENT)

    def url(self, user, suffix=''):
        return f'/api/auth/admin/users/{user.id}/{suffix}'

    def refresh_token_for(self, email):
        self.client.force_authenticate(None)
        resp = self.client.post('/api/auth/login/', {'email': email, 'password': 'x'},
                                format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        return resp.data['tokens']['refresh']

    def test_demoting_an_admin_clears_superuser_flags(self):
        self.client.force_authenticate(self.admin)
        resp = self.client.patch(self.url(self.second), {'role': 'instructor'}, format='json')
        self.assertEqual(resp.status_code, 200, resp.data)
        self.second.refresh_from_db()
        self.assertFalse(self.second.is_superuser)
        self.assertFalse(self.second.is_staff)
        self.client.force_authenticate(self.second)
        self.assertEqual(self.client.get('/api/auth/admin/users/').status_code, 403)

    def test_promoting_to_admin_sets_staff_flag(self):
        self.client.force_authenticate(self.admin)
        self.client.patch(self.url(self.student), {'role': 'admin'}, format='json')
        self.student.refresh_from_db()
        self.assertTrue(self.student.is_staff)

    def test_password_reset_revokes_existing_sessions(self):
        refresh = self.refresh_token_for('student@test.com')
        self.client.force_authenticate(self.admin)
        self.assertEqual(self.client.post(self.url(self.student, 'reset-password/')).status_code,
                         200)
        self.client.force_authenticate(None)
        resp = self.client.post('/api/auth/token/refresh/', {'refresh': refresh}, format='json')
        self.assertEqual(resp.status_code, 401)

    def test_deactivation_revokes_existing_sessions(self):
        refresh = self.refresh_token_for('student@test.com')
        self.client.force_authenticate(self.admin)
        self.client.patch(self.url(self.student), {'is_active': False}, format='json')
        self.client.force_authenticate(None)
        resp = self.client.post('/api/auth/token/refresh/', {'refresh': refresh}, format='json')
        self.assertEqual(resp.status_code, 401)
