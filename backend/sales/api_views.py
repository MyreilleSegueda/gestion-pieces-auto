from decimal import Decimal
from uuid import UUID, uuid4

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.db.models import Sum
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import BasePermission, SAFE_METHODS
from rest_framework.response import Response

from accounts.role_permissions import has_module_access
from caisse.models import Encaissement, Remboursement
from inventory.models import MouvementStock, PieceDetachee
from invoicing.models import Facture
from accounts.role_permissions import ADMINISTRATOR_ROLE

from .models import LigneRetourVente, LigneVente, RetourVente, Vente
from .serializers import (
    RetourVenteCreateSerializer,
    RetourVenteSerializer,
    VenteCreateSerializer,
    VenteDraftUpdateSerializer,
    VenteSerializer,
)


class IsSaleReaderOrSeller(BasePermission):
    def has_permission(self, request, view):
        user = request.user
        return has_module_access(user, "ventes", write=request.method not in SAFE_METHODS)


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

    def get_permissions(self):
        if self.action in {"autoriser", "refuser"}:
            return [IsAdministrator()]
        return [permission() for permission in self.permission_classes]

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

    @action(detail=True, methods=["post"], url_path="demander-annulation")
    def demander_annulation(self, request, pk=None):
        sale = self.get_object()
        return self._create_sale_adjustment(
            request,
            sale,
            {
                "vente": sale.pk,
                "type_operation": RetourVente.ANNULATION,
                "motif": request.data.get("motif", ""),
            },
        )

    def _create_sale_adjustment(self, request, sale, data):
        serializer = RetourVenteCreateSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        raw_key = request.headers.get("Idempotency-Key")
        if not raw_key:
            raise ValidationError({
                "idempotency_key": "L'en-tête Idempotency-Key est obligatoire."
            })
        try:
            key = UUID(raw_key)
        except (TypeError, ValueError, AttributeError) as error:
            raise ValidationError({
                "idempotency_key": "L'en-tête Idempotency-Key doit contenir un UUID."
            }) from error

        with transaction.atomic():
            sale = Vente.objects.select_for_update().get(pk=sale.pk)
            existing = RetourVente.objects.filter(idempotency_key=key).first()
            if existing is not None:
                if (
                    existing.vente_id != sale.pk
                    or existing.type_operation != serializer.validated_data["type_operation"]
                    or existing.motif != serializer.validated_data["motif"]
                ):
                    return Response(
                        {"detail": "Cette clé a déjà été utilisée pour une autre opération."},
                        status=status.HTTP_409_CONFLICT,
                    )
                return Response(RetourVenteSerializer(existing).data)

            if sale.statut != "VALIDEE":
                raise ValidationError("Seule une vente validée peut être retournée.")
            if sale.retours.filter(statut=RetourVente.EN_ATTENTE).exists():
                raise ValidationError(
                    "Une autre demande de retour ou d'annulation est déjà en attente."
                )

            operation_type = serializer.validated_data["type_operation"]
            if operation_type == RetourVente.ANNULATION and sale.retours.filter(
                type_operation=RetourVente.ANNULATION
            ).exists():
                raise ValidationError("Une annulation a déjà été demandée pour cette vente.")

            sale_lines = list(
                LigneVente.objects.select_for_update()
                .filter(vente=sale)
                .select_related("piece")
                .order_by("pk")
            )
            returned_quantities = {
                row["lignes__ligne_vente_id"]: row["total"]
                for row in sale.retours.exclude(
                    statut=RetourVente.REFUSE
                ).values("lignes__ligne_vente_id").annotate(
                    total=Sum("lignes__quantite")
                )
                if row["lignes__ligne_vente_id"] is not None
            }

            if operation_type == RetourVente.ANNULATION:
                if serializer.validated_data.get("lignes"):
                    raise ValidationError(
                        "Une annulation retourne automatiquement toutes les quantités restantes."
                    )
                requested_lines = [
                    {
                        "ligne_vente": line,
                        "quantite": (
                            line.quantite - returned_quantities.get(line.pk, 0)
                        ),
                    }
                    for line in sale_lines
                    if line.quantite - returned_quantities.get(line.pk, 0) > 0
                ]
            else:
                request_items = serializer.validated_data.get("lignes", [])
                if not request_items:
                    raise ValidationError("Ajoutez au moins une ligne et une quantité à retourner.")
                if len({item["ligne_vente"] for item in request_items}) != len(request_items):
                    raise ValidationError("Une ligne de vente ne peut apparaître qu'une fois.")
                sale_lines_by_id = {line.pk: line for line in sale_lines}
                requested_lines = []
                for item in request_items:
                    line = sale_lines_by_id.get(item["ligne_vente"])
                    if line is None:
                        raise ValidationError("Une ligne ne correspond pas à cette vente.")
                    remaining = line.quantite - returned_quantities.get(line.pk, 0)
                    if item["quantite"] > remaining:
                        raise ValidationError(
                            f"Quantité retournée supérieure au solde de "
                            f"{line.reference_piece} ({remaining} restante(s))."
                        )
                    requested_lines.append({
                        "ligne_vente": line,
                        "quantite": item["quantite"],
                    })

            if not requested_lines:
                raise ValidationError("Aucune quantité ne reste à retourner.")

            record = RetourVente.objects.create(
                reference=f"RET-{uuid4().hex[:12].upper()}",
                vente=sale,
                type_operation=operation_type,
                motif=serializer.validated_data["motif"],
                demande_par=request.user,
                idempotency_key=key,
            )
            LigneRetourVente.objects.bulk_create([
                LigneRetourVente(
                    retour=record,
                    ligne_vente=item["ligne_vente"],
                    reference_piece=item["ligne_vente"].reference_piece,
                    designation=item["ligne_vente"].designation,
                    quantite=item["quantite"],
                    prix_unitaire=item["ligne_vente"].prix_unitaire,
                )
                for item in requested_lines
            ])

        return Response(
            RetourVenteSerializer(record).data,
            status=status.HTTP_201_CREATED,
        )


class IsAdministrator(BasePermission):
    message = "Seul un Administrateur peut autoriser ou refuser un retour."

    def has_permission(self, request, view):
        user = request.user
        return bool(
            user.is_authenticated
            and (
                user.is_superuser
                or user.groups.filter(name=ADMINISTRATOR_ROLE).exists()
            )
        )


class RetourVenteViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    viewsets.GenericViewSet,
):
    queryset = RetourVente.objects.select_related(
        "vente",
        "demande_par",
        "autorise_par",
    ).prefetch_related("lignes")
    permission_classes = [IsSaleReaderOrSeller]
    serializer_class = RetourVenteSerializer

    def create(self, request, *args, **kwargs):
        serializer = RetourVenteCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        sale = serializer.validated_data["vente"]
        return VenteViewSet._create_sale_adjustment(
            self,
            request,
            sale,
            request.data,
        )

    def get_permissions(self):
        if self.action in {"autoriser", "refuser"}:
            return [IsAdministrator()]
        return [permission() for permission in self.permission_classes]

    @action(detail=True, methods=["post"])
    def autoriser(self, request, pk=None):
        restock_value = request.data.get("remise_en_stock")
        if not isinstance(restock_value, bool):
            raise ValidationError({
                "remise_en_stock": "Précise si les articles retournés peuvent être remis en stock."
            })

        with transaction.atomic():
            record = get_object_or_404(
                RetourVente.objects.select_for_update().select_related("vente"),
                pk=pk,
            )
            sale = Vente.objects.select_for_update().get(pk=record.vente_id)
            if record.statut == RetourVente.AUTORISE:
                return Response(RetourVenteSerializer(record).data)
            if record.statut != RetourVente.EN_ATTENTE:
                return Response(
                    {"detail": "Seule une demande en attente peut être autorisée."},
                    status=status.HTTP_409_CONFLICT,
                )

            record.remise_en_stock = restock_value
            if restock_value:
                lines = list(
                    record.lignes.select_related("ligne_vente__piece")
                    .order_by("ligne_vente__piece_id")
                )
                pieces = {
                    item.pk: item
                    for item in PieceDetachee.objects.select_for_update().filter(
                        pk__in=[line.ligne_vente.piece_id for line in lines]
                    ).order_by("pk")
                }
                for line in lines:
                    piece = pieces[line.ligne_vente.piece_id]
                    try:
                        MouvementStock.objects.create(
                            piece=piece,
                            type_mouvement="RETOUR",
                            quantite=line.quantite,
                            prix_unitaire=line.prix_unitaire,
                            motif=f"{record.get_type_operation_display()} {record.reference}",
                            reference_document=record.reference,
                            utilisateur=request.user,
                        )
                    except DjangoValidationError as error:
                        raise ValidationError(error.messages) from error

            record.statut = RetourVente.AUTORISE
            record.autorise_par = request.user
            record.date_decision = timezone.now()
            record.save(update_fields=[
                "statut",
                "remise_en_stock",
                "autorise_par",
                "date_decision",
            ])

            if record.type_operation == RetourVente.ANNULATION:
                sale.statut = "ANNULEE"
                sale.save(update_fields=["statut"])

            try:
                invoice = Facture.objects.get(vente=sale)
            except Facture.DoesNotExist as error:
                raise ValidationError(
                    "La facture associée à la vente est introuvable."
                ) from error

            refund_amount = min(
                record.montant_total,
                sum(
                    (
                        payment.montant
                        for payment in Encaissement.objects.select_for_update()
                        .filter(facture=invoice)
                        .order_by("date_encaissement", "pk")
                    ),
                    start=Decimal("0.00"),
                ),
            )
            payments = list(
                Encaissement.objects.select_for_update()
                .filter(facture=invoice)
                .prefetch_related("remboursements")
                .order_by("date_encaissement", "pk")
            )
            for payment in payments:
                if refund_amount <= 0:
                    break
                reserved = sum(
                    (
                        refund.montant
                        for refund in payment.remboursements.all()
                        if refund.statut != Remboursement.REFUSE
                    ),
                    start=Decimal("0.00"),
                )
                available = max(payment.montant - reserved, Decimal("0.00"))
                amount = min(available, refund_amount)
                if amount <= 0:
                    continue
                Remboursement.objects.create(
                    encaissement=payment,
                    retour_vente=record,
                    montant=amount,
                    motif=f"Remboursement suite au {record.get_type_operation_display()} {record.reference}",
                    mode_remboursement=payment.mode_paiement,
                    demande_par=request.user,
                )
                refund_amount -= amount

        return Response(
            RetourVenteSerializer(
                record,
                context=self.get_serializer_context(),
            ).data
        )

    @action(detail=True, methods=["post"])
    def refuser(self, request, pk=None):
        with transaction.atomic():
            record = get_object_or_404(
                RetourVente.objects.select_for_update(),
                pk=pk,
            )
            if record.statut == RetourVente.REFUSE:
                return Response(RetourVenteSerializer(record).data)
            if record.statut != RetourVente.EN_ATTENTE:
                return Response(
                    {"detail": "Une opération autorisée ne peut pas être refusée."},
                    status=status.HTTP_409_CONFLICT,
                )
            record.statut = RetourVente.REFUSE
            record.autorise_par = request.user
            record.date_decision = timezone.now()
            record.save(update_fields=["statut", "autorise_par", "date_decision"])
        return Response(RetourVenteSerializer(record).data)
