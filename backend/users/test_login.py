from django.core.cache import cache
from django.test import override_settings
from rest_framework.test import APITestCase

from users.models import User


@override_settings(RATELIMIT_ENABLE=True)
class LoginRateLimitTests(APITestCase):
    def setUp(self):
        cache.clear()
        for i in range(25):
            User.objects.create_user(email=f'u{i}@test.com', password='secret1',
                                     role=User.Role.STUDENT, first_name='U', last_name='T')

    def test_a_classroom_behind_one_ip_can_log_in(self):
        statuses = [
            self.client.post('/api/auth/login/', {'email': f'u{i}@test.com', 'password': 'secret1'},
                             format='json').status_code
            for i in range(25)
        ]
        self.assertEqual(statuses, [200] * 25)

    def test_one_account_is_still_protected_from_brute_force(self):
        statuses = [
            self.client.post('/api/auth/login/', {'email': 'u0@test.com', 'password': 'wrong'},
                             format='json').status_code
            for _ in range(12)
        ]
        self.assertIn(429, statuses)
        self.assertEqual(statuses[0], 401)

    def test_other_accounts_are_unaffected_by_one_locked_account(self):
        for _ in range(12):
            self.client.post('/api/auth/login/', {'email': 'u0@test.com', 'password': 'wrong'},
                             format='json')
        resp = self.client.post('/api/auth/login/', {'email': 'u1@test.com', 'password': 'secret1'},
                                format='json')
        self.assertEqual(resp.status_code, 200)


class LoginRecordsLastLoginTests(APITestCase):
    def test_successful_login_updates_last_login(self):
        user = User.objects.create_user(email='s@test.com', password='secret1',
                                        role=User.Role.STUDENT, first_name='S', last_name='T')
        self.assertIsNone(user.last_login)

        resp = self.client.post('/api/auth/login/', {'email': 's@test.com', 'password': 'secret1'},
                                format='json')
        self.assertEqual(resp.status_code, 200, resp.data)

        user.refresh_from_db()
        self.assertIsNotNone(user.last_login)

    def test_failed_login_does_not_touch_last_login(self):
        user = User.objects.create_user(email='s@test.com', password='secret1',
                                        role=User.Role.STUDENT, first_name='S', last_name='T')
        resp = self.client.post('/api/auth/login/', {'email': 's@test.com', 'password': 'wrong'},
                                format='json')
        self.assertEqual(resp.status_code, 401)
        user.refresh_from_db()
        self.assertIsNone(user.last_login)
