import pytest
from django.db import ProgrammingError, transaction
from rest_framework.response import Response
from rest_framework.test import APIRequestFactory, force_authenticate

from tenancy.api import TenantScopedAPIView
from tenancy.models import Camera
from tenancy.rls import current_tenant_id, resolve_camera, set_tenant_context, tenant_context


@pytest.fixture
def cameras(camera_a, camera_b):
    # Created as the owner (bypasses RLS), before switching to the app role.
    return camera_a, camera_b


def external_ids():
    return sorted(Camera.objects.values_list('external_id', flat=True))


# --- Role sanity -------------------------------------------------------------

def test_owner_bypasses_rls(cameras):
    """The owner (migrations, SECURITY DEFINER) is deliberately not filtered."""
    assert external_ids() == ['cam_1001', 'cam_2050']


# --- RLS as the app role -----------------------------------------------------

def test_no_tenant_context_sees_nothing(cameras, app_role):
    assert external_ids() == []


def test_each_tenant_sees_only_its_cameras(cameras, app_role, tenant_a, tenant_b):
    with tenant_context(tenant_a.id):
        assert external_ids() == ['cam_1001']
    with tenant_context(tenant_b.id):
        assert external_ids() == ['cam_2050']


def test_cannot_insert_camera_for_another_tenant(cameras, app_role, tenant_a, tenant_b):
    with pytest.raises(ProgrammingError, match='row-level security'):
        with tenant_context(tenant_a.id):
            Camera.objects.create(external_id='cam_spoof', tenant=tenant_b)


def test_cannot_update_or_delete_another_tenants_camera(cameras, app_role, tenant_a):
    with tenant_context(tenant_a.id):
        assert Camera.objects.filter(external_id='cam_2050').update(label='hijacked') == 0
        assert Camera.objects.filter(external_id='cam_2050').delete()[0] == 0


def test_cannot_move_own_camera_to_another_tenant(cameras, app_role, tenant_a, tenant_b):
    with pytest.raises(ProgrammingError, match='row-level security'):
        with tenant_context(tenant_a.id):
            Camera.objects.filter(external_id='cam_1001').update(tenant=tenant_b)


def test_resolve_camera_works_without_tenant_context(cameras, app_role, camera_b):
    resolved = resolve_camera('cam_2050')

    assert resolved.id == camera_b.id
    assert resolved.tenant_id == camera_b.tenant_id
    assert resolved.is_active is True
    assert resolve_camera('cam_unknown') is None


# --- Tenant context helpers --------------------------------------------------

def test_nested_context_restores_outer_tenant(app_role, tenant_a, tenant_b):
    with tenant_context(tenant_a.id):
        with tenant_context(tenant_b.id):
            assert current_tenant_id() == tenant_b.id
        assert current_tenant_id() == tenant_a.id
    assert current_tenant_id() is None


def test_failed_nested_context_restores_outer_tenant(app_role, tenant_a, tenant_b):
    with tenant_context(tenant_a.id):
        with pytest.raises(ValueError):
            with tenant_context(tenant_b.id):
                raise ValueError
        assert current_tenant_id() == tenant_a.id


@pytest.mark.django_db(transaction=True)
def test_set_tenant_context_refuses_to_run_outside_a_transaction(tenant_a):
    assert not transaction.get_connection().in_atomic_block
    with pytest.raises(RuntimeError):
        set_tenant_context(tenant_a.id)


# --- TenantScopedAPIView -----------------------------------------------------

class ProbeView(TenantScopedAPIView):
    def get(self, request):
        return Response({
            'request_tenant': request.tenant.id,
            'db_tenant': current_tenant_id(),
            'cameras': external_ids(),
        })


@pytest.mark.parametrize('who, expected_camera', [('a', 'cam_1001'), ('b', 'cam_2050')])
def test_scoped_view_sets_request_and_db_tenant(cameras, user_a, user_b, app_role, who, expected_camera):
    user = {'a': user_a, 'b': user_b}[who]
    request = APIRequestFactory().get('/probe')
    force_authenticate(request, user=user)

    with transaction.atomic():  # what ATOMIC_REQUESTS wraps around a real request
        response = ProbeView.as_view()(request)

    assert response.status_code == 200
    assert response.data['request_tenant'] == user.tenant_id
    assert response.data['db_tenant'] == user.tenant_id
    assert response.data['cameras'] == [expected_camera]


@pytest.mark.django_db(transaction=True)
def test_scoped_view_context_ends_with_request_transaction(user_a):
    """
    Needs a real (outermost) transaction: inside the test's own transaction
    the request's atomic() is only a savepoint, and a transaction-local
    setting survives until the outermost transaction ends.
    """
    request = APIRequestFactory().get('/probe')
    force_authenticate(request, user=user_a)

    with transaction.atomic():
        response = ProbeView.as_view()(request)
        assert current_tenant_id() == user_a.tenant_id

    assert response.status_code == 200
    assert current_tenant_id() is None


def test_scoped_view_rejects_anonymous(app_role):
    response = ProbeView.as_view()(APIRequestFactory().get('/probe'))
    assert response.status_code == 401
