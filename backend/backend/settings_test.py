"""
Test settings. Tests connect as the owner role, the only one allowed to create
the test database. The owner bypasses RLS, so tests that exercise RLS switch to
the app role with the `app_role` fixture (see conftest.py).
"""

import os

from .settings import *  # noqa: F401,F403
from .settings import DATABASES

DATABASES['default'].update(
    USER=os.environ.get('DB_OWNER_USER', 'app_owner'),
    PASSWORD=os.environ.get('DB_OWNER_PASSWORD', 'app_owner_pw'),
)

APP_DB_ROLE = os.environ.get('DB_APP_USER', 'app_rw')

# Hashing at full strength makes every login in a test take ~1s.
PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']
