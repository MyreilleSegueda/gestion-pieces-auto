
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db import transaction
from django.db.models import Q
from rest_framework import status, viewsets
from rest_framework.permissions import BasePermission
from rest_framework.decorators import action
from rest_framework.response import Response

from accounts.role_permissions import (
    ROLE_MODULE_ACCESS,
    is_administrator,
)

from .serializers import NewPasswordSerializer, RoleSerializer, UtilisateurSerializer

User = get_user_model()


class IsAdministrateur(BasePermission):
    def has_permission(self, request, view):
        return is_administrator(request.user)


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
            .filter(
                Q(is_superuser=True)
                | Q(groups__name="Administrateur")
            )
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

    @action(detail=True, methods=["post"], url_path="reinitialiser-mot-de-passe")
    def reinitialiser_mot_de_passe(self, request, pk=None):
        user = self.get_object()
        if user.pk == request.user.pk:
            return Response(
                {"detail": "Utilise le changement de mot de passe de ton profil."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        serializer = NewPasswordSerializer(
            data=request.data,
            context={"target_user": user},
        )
        serializer.is_valid(raise_exception=True)
        user.set_password(serializer.validated_data["new_password"])
        user.save(update_fields=["password"])
        return Response(
            {"detail": "Le mot de passe a été réinitialisé."},
            status=status.HTTP_200_OK,
        )


class RoleViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Group.objects.all().order_by("name")
    serializer_class = RoleSerializer
    permission_classes = [IsAdministrateur]

    @action(detail=False, methods=["get"], url_path="effectifs")
    def effectifs(self, request):
        modules_par_defaut = {
            "utilisateurs": "aucun",
            "stock": "aucun",
            "clients": "aucun",
            "fournisseurs": "aucun",
            "ventes": "aucun",
            "factures": "aucun",
            "rapports": "aucun",
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
                "is_staff_grants_business_access": False,
            }
            for group in groups
        ])
