"""
Base classes for every authenticated, tenant-scoped API view.

Why here and not in a middleware: Django middleware runs before DRF
authenticates the request, so with JWT `request.user` is still anonymous at
that point. DRF's `initial()` runs after authentication and permission checks,
and inside the request transaction (ATOMIC_REQUESTS), which is exactly where
the transaction-local RLS setting has to be made.
"""

from rest_framework import generics, viewsets
from rest_framework.views import APIView

from .rls import set_tenant_context


class TenantScopedMixin:
    """
    After authentication, pins the request to the user's tenant:
      - `request.tenant` for application-level filtering (layer 1)
      - `app.tenant_id` in Postgres for row-level security (layer 2)
    """

    def initial(self, request, *args, **kwargs):
        # Authenticates and enforces permissions (IsAuthenticated by default),
        # so past this line request.user is a real, active user.
        super().initial(request, *args, **kwargs)
        request.tenant = request.user.tenant
        set_tenant_context(request.tenant.id)


class TenantScopedAPIView(TenantScopedMixin, APIView):
    pass


class TenantScopedGenericAPIView(TenantScopedMixin, generics.GenericAPIView):
    pass


class TenantScopedViewSet(TenantScopedMixin, viewsets.GenericViewSet):
    pass
