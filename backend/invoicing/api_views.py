from decimal import Decimal

from django.db.models import (
    DecimalField,
    ExpressionWrapper,
    F,
    OuterRef,
    Subquery,
    Sum,
    Value,
)
from django.db.models.functions import Coalesce
from rest_framework import viewsets
from rest_framework.permissions import BasePermission

from accounts.role_permissions import has_module_access
from caisse.models import Encaissement, Remboursement
from sales.models import LigneRetourVente, RetourVente
from .models import Facture
from .serializers import FactureSerializer


AMOUNT_FIELD = DecimalField(max_digits=14, decimal_places=2)


class InvoiceReaderPermission(BasePermission):
    def has_permission(self, request, view):
        return has_module_access(request.user, "factures")


class FactureViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Facture.objects.select_related(
        "vente",
        "vente__client",
        "emise_par",
    ).prefetch_related(
        "vente__lignes",
        "encaissements__encaisse_par",
    ).annotate(
        total_encaisse=Coalesce(
            Subquery(
                Encaissement.objects.filter(facture_id=OuterRef("pk"))
                .values("facture_id")
                .annotate(total=Sum("montant"))
                .values("total")[:1]
            ),
            Value(Decimal("0.00"), output_field=AMOUNT_FIELD),
        ),
        total_rembourse=Coalesce(
            Subquery(
                Remboursement.objects.filter(
                    encaissement__facture_id=OuterRef("pk"),
                    statut=Remboursement.EXECUTE,
                )
                .values("encaissement__facture_id")
                .annotate(total=Sum("montant"))
                .values("total")[:1]
            ),
            Value(Decimal("0.00"), output_field=AMOUNT_FIELD),
        ),
        total_avoirs=Coalesce(
            Subquery(
                LigneRetourVente.objects.filter(
                    retour__vente_id=OuterRef("vente_id"),
                    retour__statut=RetourVente.AUTORISE,
                )
                .values("retour__vente_id")
                .annotate(
                    total=Sum(
                        ExpressionWrapper(
                            F("quantite") * F("prix_unitaire"),
                            output_field=AMOUNT_FIELD,
                        )
                    )
                )
                .values("total")[:1]
            ),
            Value(Decimal("0.00"), output_field=AMOUNT_FIELD),
        ),
    )
    serializer_class = FactureSerializer
    permission_classes = [InvoiceReaderPermission]
