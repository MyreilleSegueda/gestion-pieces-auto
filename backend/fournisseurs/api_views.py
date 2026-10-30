from rest_framework import viewsets
from rest_framework.permissions import BasePermission, SAFE_METHODS

from accounts.role_permissions import roles_with_write_access
from .models import Fournisseur
from .serializers import FournisseurSerializer


class IsSupplierReaderOrManager(BasePermission):
    roles_fournisseurs = roles_with_write_access("fournisseurs")

    def has_permission(self, request, view):
        user = request.user
        if not user.is_authenticated:
            return False
        if request.method in SAFE_METHODS:
            return True
        return user.is_staff or user.groups.filter(
            name__in=self.roles_fournisseurs
        ).exists()


class FournisseurViewSet(viewsets.ModelViewSet):
    queryset = Fournisseur.objects.all()
    serializer_class = FournisseurSerializer
    permission_classes = [IsSupplierReaderOrManager]
    http_method_names = ["get", "post", "put", "patch", "head", "options"]
