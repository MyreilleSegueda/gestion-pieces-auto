from uuid import NAMESPACE_URL, uuid5

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework import viewsets
from rest_framework.permissions import BasePermission, SAFE_METHODS

from accounts.role_permissions import has_module_access
from inventory.models import MouvementStock, PieceDetachee
from .models import AchatFournisseur, Fournisseur
from .serializers import (
    AchatFournisseurCreateSerializer,
    AchatFournisseurSerializer,
    FournisseurSerializer,
)


class IsSupplierReaderOrManager(BasePermission):
    def has_permission(self, request, view):
        user = request.user
        return has_module_access(
            user,
            "fournisseurs",
            write=request.method not in SAFE_METHODS,
        )


class FournisseurViewSet(viewsets.ModelViewSet):
    queryset = Fournisseur.objects.all()
    serializer_class = FournisseurSerializer
    permission_classes = [IsSupplierReaderOrManager]
    http_method_names = ["get", "post", "put", "patch", "head", "options"]


class AchatFournisseurViewSet(viewsets.GenericViewSet):
    queryset = AchatFournisseur.objects.select_related(
        "fournisseur",
        "cree_par",
        "recu_par",
    ).prefetch_related("lignes")
    permission_classes = [IsSupplierReaderOrManager]
    serializer_class = AchatFournisseurSerializer
    http_method_names = ["get", "post", "head", "options"]

    def list(self, request):
        purchases = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(purchases)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        return Response(self.get_serializer(purchases, many=True).data)

    def retrieve(self, request, pk=None):
        purchase = self.get_object()
        return Response(self.get_serializer(purchase).data)

    def create(self, request):
        serializer = AchatFournisseurCreateSerializer(
            data=request.data,
            context=self.get_serializer_context(),
        )
        serializer.is_valid(raise_exception=True)
        purchase = serializer.save()
        return Response(
            self.get_serializer(purchase).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["post"])
    def recevoir(self, request, pk=None):
        with transaction.atomic():
            purchase = get_object_or_404(
                AchatFournisseur.objects.select_for_update(),
                pk=pk,
            )
            if purchase.statut == AchatFournisseur.RECU:
                return Response(self.get_serializer(purchase).data)

            lines = list(
                purchase.lignes.select_related("piece")
                .order_by("piece_id")
            )
            if not lines:
                raise ValidationError("Un achat sans article ne peut pas être réceptionné.")
            pieces = {
                piece.pk: piece
                for piece in PieceDetachee.objects.select_for_update().filter(
                    pk__in=[line.piece_id for line in lines]
                ).order_by("pk")
            }
            for line in lines:
                try:
                    MouvementStock.objects.create(
                        piece=pieces[line.piece_id],
                        type_mouvement="ENTREE",
                        quantite=line.quantite,
                        prix_unitaire=line.prix_unitaire,
                        motif=f"Réception achat {purchase.reference}",
                        reference_document=purchase.reference,
                        utilisateur=request.user,
                        idempotency_key=uuid5(
                            NAMESPACE_URL,
                            f"achat-fournisseur:{purchase.pk}:ligne:{line.pk}",
                        ),
                    )
                except DjangoValidationError as error:
                    raise ValidationError(error.messages) from error

            purchase.statut = AchatFournisseur.RECU
            purchase.recu_par = request.user
            purchase.date_reception = timezone.now()
            purchase.save(update_fields=["statut", "recu_par", "date_reception"])

        return Response(self.get_serializer(purchase).data)
