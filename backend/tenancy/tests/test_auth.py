import pytest
from rest_framework_simplejwt.tokens import AccessToken

# Auth must work for the runtime role: users/tenants have no RLS (login runs
# before any tenant is known), but the role still needs its grants.
pytestmark = pytest.mark.usefixtures('app_role')


@pytest.fixture
def users(user_a, user_b):
    return user_a, user_b


def test_login_returns_tokens_without_tenant_claim(api, users):
    response = api.post('/api/v1/auth/login', {'username': 'alice', 'password': 'pw-alice'}, format='json')

    assert response.status_code == 200
    assert set(response.data) == {'access', 'refresh'}
    claims = AccessToken(response.data['access']).payload
    assert 'tenant' not in claims and 'tenant_id' not in claims


def test_login_rejects_wrong_password(api, users):
    response = api.post('/api/v1/auth/login', {'username': 'alice', 'password': 'nope'}, format='json')
    assert response.status_code == 401


def test_login_rejects_inactive_user(api, users, user_a):
    user_a.is_active = False
    user_a.save(update_fields=['is_active'])

    response = api.post('/api/v1/auth/login', {'username': 'alice', 'password': 'pw-alice'}, format='json')
    assert response.status_code == 401


def test_refresh_returns_new_access_token(api, users):
    tokens = api.post('/api/v1/auth/login', {'username': 'alice', 'password': 'pw-alice'}, format='json').data

    response = api.post('/api/v1/auth/refresh', {'refresh': tokens['refresh']}, format='json')

    assert response.status_code == 200
    assert 'access' in response.data


@pytest.mark.parametrize('username, password, tenant_slug', [
    ('alice', 'pw-alice', 'peachtree'),
    ('bob', 'pw-bob', 'blue-ridge'),
])
def test_me_returns_own_tenant(login, users, username, password, tenant_slug):
    response = login(username, password).get('/api/v1/me')

    assert response.status_code == 200
    assert response.data['username'] == username
    assert response.data['role'] == 'staff'
    assert response.data['tenant']['slug'] == tenant_slug


def test_me_requires_token(api):
    assert api.get('/api/v1/me').status_code == 401


def test_me_rejects_garbage_token(api):
    api.credentials(HTTP_AUTHORIZATION='Bearer not.a.jwt')
    assert api.get('/api/v1/me').status_code == 401
