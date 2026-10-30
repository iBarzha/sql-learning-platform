from django.test import RequestFactory, SimpleTestCase

from config.middleware import RealIPMiddleware


class RealIPMiddlewareTests(SimpleTestCase):
    def setUp(self):
        self.seen = {}
        self.middleware = RealIPMiddleware(
            lambda request: self.seen.setdefault('addr', request.META['REMOTE_ADDR']))
        self.factory = RequestFactory()

    def test_uses_x_real_ip_when_present(self):
        request = self.factory.get('/', REMOTE_ADDR='172.18.0.5', HTTP_X_REAL_IP='203.0.113.9')
        self.middleware(request)
        self.assertEqual(self.seen['addr'], '203.0.113.9')

    def test_keeps_remote_addr_without_header(self):
        request = self.factory.get('/', REMOTE_ADDR='172.18.0.5')
        self.middleware(request)
        self.assertEqual(self.seen['addr'], '172.18.0.5')

    def test_blank_header_is_ignored(self):
        request = self.factory.get('/', REMOTE_ADDR='172.18.0.5', HTTP_X_REAL_IP='  ')
        self.middleware(request)
        self.assertEqual(self.seen['addr'], '172.18.0.5')
