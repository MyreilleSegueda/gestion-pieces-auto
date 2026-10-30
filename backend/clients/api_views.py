from rest_framework import viewsets
from rest_framework.permissions import BasePermission, SAFE_METHODS

from accounts.role_permissions import roles_with_write_access
from .models import Client
from .serializers import ClientSerializer


class IsClientReaderOrManager(BasePermission):
    roles_clients = roles_with_write_access("clients")

    def has_permission(self, request, view):
        user = request.user
        if not user.is_authenticated:
            return False
        if request.method in SAFE_METHODS:
            return True
        return user.is_staff or user.groups.filter(name__in=self.roles_clients).exists()


class ClientViewSet(viewsets.ModelViewSet):
    queryset = Client.objects.all()
    serializer_class = ClientSerializer
    permission_classes = [IsClientReaderOrManager]
    http_method_names = ["get", "post", "put", "patch", "head", "options"]
