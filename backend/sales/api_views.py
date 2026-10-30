from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import BasePermission, SAFE_METHODS
from rest_framework.response import Response

from accounts.role_permissions import roles_with_write_access
from inventory.models import MouvementStock, PieceDetachee

from .models import Vente
from .serializers import (
    VenteCreateSerializer,
    VenteDraftUpdateSerializer,
    VenteSerializer,
)


class IsSaleReaderOrSeller(BasePermission):
    roles_vente = roles_with_write_access("ventes")

    def has_permission(self, request, view):
        user = request.user
        if not user.is_authenticated:
            return False
        if request.method in SAFE_METHODS:
            return True
        return user.is_staff or user.groups.filter(name__in=self.roles_vente).exists()


class VenteViewSet(viewsets.ModelViewSet):
    queryset = Vente.objects.select_related("client", "creee_par").prefetch_related("lignes")
    permission_classes = [IsSaleReaderOrSeller]
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_serializer_class(self):
        if self.action == "create":
            return VenteCreateSerializer
        if self.action == "partial_update":
            return VenteDraftUpdateSerializer
        return VenteSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        sale = serializer.save(creee_par=request.user)
        return Response(
            VenteSerializer(sale).data,
            status=status.HTTP_201_CREATED,
        )

    def perform_create(self, serializer):
        serializer.save(creee_par=self.request.user)

    def partial_update(self, request, *args, **kwargs):
        with transaction.atomic():
            try:
                sale = Vente.objects.select_for_update().get(pk=kwargs["pk"])
            except Vente.DoesNotExist as error:
                raise ValidationError("Vente introuvable.") from error

            if sale.statut != "BROUILLON":
                return Response(
                    {"detail": "Seule une vente brouillon peut être modifiée."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            serializer = self.get_serializer(
                sale,
                data=request.data,
                partial=True,
            )
            serializer.is_valid(raise_exception=True)
            sale = serializer.save()

        return Response(VenteSerializer(sale).data)

    @action(detail=True, methods=["post"])
    def valider(self, request, pk=None):
        try:
            with transaction.atomic():
                sale = Vente.objects.select_for_update().get(pk=pk)
                if sale.statut != "BROUILLON":
                    return Response(
                        {"detail": "Seule une vente brouillon peut être validée."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                lines = list(sale.lignes.select_related("piece").order_by("piece_id"))
                pieces = {
                    piece.pk: piece
                    for piece in PieceDetachee.objects.select_for_update().filter(
                        pk__in=[line.piece_id for line in lines]
                    ).order_by("pk")
                }
                for line in lines:
                    piece = pieces[line.piece_id]
                    if not piece.actif:
                        raise ValidationError(
                            f"La pièce {piece.reference} est désactivée."
                        )
                    if line.quantite > piece.quantite_stock:
                        raise ValidationError(
                            f"Stock insuffisant pour {piece.reference} : "
                            f"{piece.quantite_stock} disponible(s)."
                        )

                for line in lines:
                    piece = pieces[line.piece_id]
                    try:
                        MouvementStock.objects.create(
                            piece=piece,
                            type_mouvement="SORTIE",
                            quantite=line.quantite,
                            prix_unitaire=line.prix_unitaire,
                            motif=f"Vente {sale.reference}",
                            reference_document=sale.reference,
                            utilisateur=request.user,
                            idempotency_key=None,
                        )
                    except DjangoValidationError as error:
                        raise ValidationError(error.messages) from error

                sale.statut = "VALIDEE"
                sale.validee_par = request.user
                sale.date_validation = timezone.now()
                sale.save(update_fields=["statut", "validee_par", "date_validation"])
                from invoicing.models import Facture

                Facture.objects.create(vente=sale, emise_par=request.user)

        except Vente.DoesNotExist as error:
            raise ValidationError("Vente introuvable.") from error

        return Response(VenteSerializer(sale).data)

    @action(detail=True, methods=["post"])
    def annuler(self, request, pk=None):
        with transaction.atomic():
            try:
                sale = Vente.objects.select_for_update().get(pk=pk)
            except Vente.DoesNotExist as error:
                raise ValidationError("Vente introuvable.") from error
            if sale.statut != "BROUILLON":
                return Response(
                    {"detail": "Une vente validée ne peut pas être annulée par cette action."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            sale.statut = "ANNULEE"
            sale.save(update_fields=["statut"])
        return Response(VenteSerializer(sale).data)
