from django.db.models import DecimalField, Value
from django.db.models.functions import Coalesce


from .serializers import FactureCaisseSerializer
from decimal import Decimal

from django.db import transaction
from django.db.models import Sum
from django.shortcuts import get_object_or_404

from rest_framework import mixins, status
from rest_framework.permissions import BasePermission
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from accounts.role_permissions import ADMINISTRATOR_ROLE
from invoicing.models import Facture
from sales.models import Vente
from .models import Encaissement
from .serializers import (
    EncaissementCreateSerializer,
    EncaissementSerializer,
)


class CaissePermission(BasePermission):
    message = "Accès réservé à l'Administrateur et au Caissier."

    def has_permission(self, request, view):
        user = request.user

        if not user or not user.is_authenticated:
            return False

        if user.is_superuser:
            return True
            

        return user.groups.filter(
            name__in=[ADMINISTRATOR_ROLE, "Caissier"]
        ).exists()


class EncaissementViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    GenericViewSet,
):
    permission_classes = [CaissePermission]

    queryset = Encaissement.objects.select_related(
        "facture",
        "facture__vente",
        "facture__vente__client",
        "encaisse_par",
    )

    def get_serializer_class(self):
        if self.action == "create":
            return EncaissementCreateSerializer
        return EncaissementSerializer

    def create(self, request, *args, **kwargs):
        input_serializer = self.get_serializer(data=request.data)
        input_serializer.is_valid(raise_exception=True)

        facture_id = input_serializer.validated_data["facture_id"]
        montant = input_serializer.validated_data["montant"]
        mode_paiement = input_serializer.validated_data["mode_paiement"]

        with transaction.atomic():
            facture = get_object_or_404(
                Facture.objects.select_for_update().select_related("vente"),
                pk=facture_id,
            )

            if facture.vente.statut != "VALIDEE":
                return Response(
                    {"detail": "Seules les ventes validées peuvent être encaissées."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            total_facture = facture.total

            total_encaisse = (
                Encaissement.objects.filter(facture=facture).aggregate(
                    total=Sum("montant")
                )["total"]
                or Decimal("0.00")
            )

            solde_restant = total_facture - total_encaisse

            if solde_restant <= 0:
                return Response(
                    {"detail": "Cette facture est déjà entièrement payée."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if montant > solde_restant:
                return Response(
                    {
                        "detail": (
                            f"Montant supérieur au solde restant "
                            f"({solde_restant:.2f})."
                        ),
                        "solde_restant": str(solde_restant),
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            encaissement = Encaissement.objects.create(
                facture=facture,
                montant=montant,
                mode_paiement=mode_paiement,
                encaisse_par=request.user,
            )

        output_serializer = EncaissementSerializer(
            encaissement,
            context=self.get_serializer_context(),
        )

        return Response(
            output_serializer.data,
            status=status.HTTP_201_CREATED,
        )

class FactureCaisseViewSet(
    mixins.ListModelMixin,
    GenericViewSet,
):
    serializer_class = FactureCaisseSerializer
    permission_classes = [CaissePermission]

    queryset = (
        Facture.objects
        .filter(vente__statut="VALIDEE")
        .select_related("vente", "vente__client")
        .prefetch_related("vente__lignes")
        .annotate(
            total_encaisse=Coalesce(
                Sum("encaissements__montant"),
                Value(
                    Decimal("0.00"),
                    output_field=DecimalField(
                        max_digits=14,
                        decimal_places=2,
                    ),
                ),
            )
        )
    )
