from rest_framework.permissions import BasePermission, SAFE_METHODS
from accounts.role_permissions import ADMINISTRATOR_ROLE


class ConfigurationMagasinPermission(BasePermission):
    message = "Seul l'Administrateur peut modifier les paramètres du magasin."

    def has_permission(self, request, view):
        user = request.user

        if not user or not user.is_authenticated:
            return False

        # Tous les utilisateurs connectés peuvent consulter
        if request.method in SAFE_METHODS:
            return True

        # Seul l'Administrateur peut modifier
        return (
            user.is_superuser
            or user.groups.filter(name=ADMINISTRATOR_ROLE).exists()
        )