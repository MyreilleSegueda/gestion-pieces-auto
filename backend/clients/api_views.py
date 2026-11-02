from rest_framework import viewsets
from rest_framework.permissions import BasePermission, SAFE_METHODS

from accounts.role_permissions import has_module_access
from .models import Client
from .serializers import ClientSerializer


class IsClientReaderOrManager(BasePermission):
    def has_permission(self, request, view):
        user = request.user
        return has_module_access(user, "clients", write=request.method not in SAFE_METHODS)


class ClientViewSet(viewsets.ModelViewSet):
    queryset = Client.objects.all()
    serializer_class = ClientSerializer
    permission_classes = [IsClientReaderOrManager]
    http_method_names = ["get", "post", "put", "patch", "head", "options"]
