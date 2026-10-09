"""Settings for the automated test suite.

SQLite keeps the suite runnable without the PostgreSQL container; the project has no
PostgreSQL-only fields. Rate limiting is off so a test can submit more than ten times.
"""

from .settings import *  # noqa: F401,F403

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    }
}

RATELIMIT_ENABLE = False

PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']

LOGGING = {'version': 1, 'disable_existing_loggers': True}
