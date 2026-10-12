import re

import pytest
from django.conf import settings
from django.db import connection
from rest_framework.test import APIClient

from tenancy.models import Camera, Tenant, User


def _app_role():
    role = settings.APP_DB_ROLE
    if not re.fullmatch(r'[a-z_][a-z0-9_]*', role):
        raise ValueError(f'Unexpected app role name: {role!r}')
    return role


@pytest.fixture(scope='session')
def django_db_setup(django_db_setup, django_db_blocker):
    """
    In the real database the app role gets its privileges from the owner's
    default privileges (db/init/01-roles.sh). Those are per-database, so the
    freshly created test database needs the same grants explicitly.
    """
    role = _app_role()
    with django_db_blocker.unblock(), connection.cursor() as cursor:
        cursor.execute(f'''
            GRANT USAGE ON SCHEMA public TO {role};
            GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {role};
            GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {role};
            GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO {role};
        ''')


@pytest.fixture
def app_role(db):
    """
    Run the rest of the test as the runtime app role, i.e. subject to RLS.
    SET LOCAL lasts until the test's transaction is rolled back. Create any
    fixture data that needs to bypass RLS before requesting this fixture.
    """
    with connection.cursor() as cursor:
        cursor.execute(f'SET LOCAL ROLE {_app_role()}')


@pytest.fixture
def tenant_a(db):
    return Tenant.objects.create(name='Peachtree Recovery', slug='peachtree')


@pytest.fixture
def tenant_b(db):
    return Tenant.objects.create(name='Blue Ridge Recovery', slug='blue-ridge')


@pytest.fixture
def user_a(tenant_a):
    return User.objects.create_user('alice', password='pw-alice', tenant=tenant_a)


@pytest.fixture
def user_b(tenant_b):
    return User.objects.create_user('bob', password='pw-bob', tenant=tenant_b)


@pytest.fixture
def camera_a(tenant_a):
    return Camera.objects.create(external_id='cam_1001', tenant=tenant_a)


@pytest.fixture
def camera_b(tenant_b):
    return Camera.objects.create(external_id='cam_2050', tenant=tenant_b)


@pytest.fixture
def api():
    return APIClient()


@pytest.fixture
def login(api):
    """login(username, password) -> APIClient authenticated with a real JWT."""
    def _login(username, password):
        response = api.post('/api/v1/auth/login', {'username': username, 'password': password}, format='json')
        assert response.status_code == 200, response.content
        api.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")
        return api
    return _login
