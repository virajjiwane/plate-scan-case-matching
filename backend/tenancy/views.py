from rest_framework.response import Response

from .api import TenantScopedAPIView
from .serializers import MeSerializer


class MeView(TenantScopedAPIView):
    """The logged-in user and the tenant they act for."""

    def get(self, request):
        return Response(MeSerializer(request.user).data)
