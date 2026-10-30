
from django.db import transaction
from django.db.models import Q
from rest_framework import viewsets
from rest_framework.permissions import BasePermission
from rest_framework.decorators import action
from rest_framework.response import Response
from django.contrib.auth.models import Group
from accounts.role_permissions import ADMINISTRATOR_ROLE, ROLE_MODULE_ACCESS

from .serializers import RoleSerializer, UtilisateurSerializer
from django.contrib.auth import get_user_model

User = get_user_model()


class IsAdministrateur(BasePermission):
    def has_permission(self, request, view):
        user = request.user
        return user.is_authenticated and (
            user.is_staff or user.groups.filter(name=ADMINISTRATOR_ROLE).exists()
        )


class UtilisateurViewSet(viewsets.ModelViewSet):
    queryset = User.objects.prefetch_related("groups").all().order_by("id")
    serializer_class = UtilisateurSerializer
    permission_classes = [IsAdministrateur]
    http_method_names = ["get", "post", "put", "patch", "head", "options"]

    @staticmethod
    def lock_active_administrators():
        list(
            User.objects.select_for_update(of=("self",))
            .filter(is_active=True)
            .filter(Q(is_staff=True) | Q(groups__name=ADMINISTRATOR_ROLE))
            .order_by("pk")
            .values_list("pk", flat=True)
        )

    def update(self, request, *args, **kwargs):
        with transaction.atomic():
            self.lock_active_administrators()
            return super().update(request, *args, **kwargs)

    def partial_update(self, request, *args, **kwargs):
        with transaction.atomic():
            self.lock_active_administrators()
            return super().partial_update(request, *args, **kwargs)


class RoleViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Group.objects.all().order_by("name")
    serializer_class = RoleSerializer
    permission_classes = [IsAdministrateur]

    @action(detail=False, methods=["get"], url_path="effectifs")
    def effectifs(self, request):
        modules_par_defaut = {
            "utilisateurs": "aucun",
            "stock": "lecture",
            "clients": "lecture",
            "fournisseurs": "lecture",
            "ventes": "lecture",
            "factures": "lecture",
            "rapports": "lecture",
            "caisse": "absent",
        }
        groups = self.get_queryset().prefetch_related("permissions__content_type")

        return Response([
            {
                "id": group.id,
                "name": group.name,
                "permissions_api": ROLE_MODULE_ACCESS.get(
                    group.name,
                    modules_par_defaut,
                ),
                "permissions_django": [
                    {
                        "app_label": permission.content_type.app_label,
                        "codename": permission.codename,
                        "name": permission.name,
                    }
                    for permission in group.permissions.all().order_by(
                        "content_type__app_label",
                        "codename",
                    )
                ],
                "is_staff_bypass_applies_to_members": True,
            }
            for group in groups
        ])
