from decimal import Decimal
from uuid import UUID

from django.db import IntegrityError, transaction
from django.db.models import DecimalField, F, OuterRef, Q, Subquery, Sum, Value
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404
from django.utils import timezone

from rest_framework import mixins, status
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import BasePermission
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from accounts.role_permissions import ADMINISTRATOR_ROLE
from invoicing.models import Facture
from sales.models import LigneRetourVente, RetourVente
from store_settings.models import ConfigurationMagasin
from .models import (
    ClotureCaisse,
    ClotureCaisseLigne,
    Encaissement,
    Remboursement,
)
from .serializers import (
    ClotureCaisseCreateSerializer,
    ClotureCaisseLigneSerializer,
    ClotureCaisseSerializer,
    EncaissementCreateSerializer,
    EncaissementSerializer,
    FactureCaisseSerializer,
    RemboursementCreateSerializer,
    RemboursementSerializer,
)


def lock_cash_day():
    day, _created = ClotureCaisse.objects.get_or_create(
        date_jour=timezone.localdate()
    )
    return ClotureCaisse.objects.select_for_update().get(pk=day.pk)


def cash_amounts_for_day(day):
    gross_totals = {
        mode: Decimal("0.00")
        for mode, _label in Encaissement.MODES_PAIEMENT
    }
    refund_totals = {
        mode: Decimal("0.00")
        for mode, _label in Encaissement.MODES_PAIEMENT
    }
    payments = (
        Encaissement.objects.filter(date_encaissement__date=day)
        .values("mode_paiement")
        .annotate(total=Sum("montant"))
    )
    for item in payments:
        gross_totals[item["mode_paiement"]] += item["total"]

    refunds = (
        Remboursement.objects.filter(
            statut=Remboursement.EXECUTE,
            date_execution__date=day,
        )
        .values("mode_remboursement")
        .annotate(total=Sum("montant"))
    )
    for item in refunds:
        refund_totals[item["mode_remboursement"]] += item["total"]

    return {
        mode: {
            "montant_encaisse": gross_totals[mode],
            "montant_rembourse": refund_totals[mode],
            "montant_theorique": gross_totals[mode] - refund_totals[mode],
        }
        for mode, _label in Encaissement.MODES_PAIEMENT
    }


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


class IsAdministrator(BasePermission):
    message = "Seul un Administrateur peut approuver ou refuser un remboursement."

    def has_permission(self, request, view):
        user = request.user
        return bool(
            user
            and user.is_authenticated
            and (
                user.is_superuser
                or user.groups.filter(name=ADMINISTRATOR_ROLE).exists()
            )
        )


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
    ).prefetch_related("remboursements")

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
        raw_key = request.headers.get("Idempotency-Key")
        if not raw_key:
            raise ValidationError({
                "idempotency_key": "L'en-tête Idempotency-Key est obligatoire."
            })
        try:
            idempotency_key = UUID(raw_key)
        except (ValueError, TypeError, AttributeError) as error:
            raise ValidationError({
                "idempotency_key": "L'en-tête Idempotency-Key doit contenir un UUID."
            }) from error

        existing = Encaissement.objects.filter(
            idempotency_key=idempotency_key
        ).first()
        if existing is not None:
            return self._idempotent_response(
                existing,
                facture_id,
                montant,
                mode_paiement,
            )

        try:
            with transaction.atomic():
                cash_day = lock_cash_day()
                existing = Encaissement.objects.filter(
                    idempotency_key=idempotency_key
                ).first()
                if existing is not None:
                    return self._idempotent_response(
                        existing,
                        facture_id,
                        montant,
                        mode_paiement,
                    )
                if cash_day.date_cloture is not None:
                    return Response(
                        {"detail": "La caisse de cette journée est déjà clôturée."},
                        status=status.HTTP_409_CONFLICT,
                    )

                facture = get_object_or_404(
                    Facture.objects.select_for_update().select_related("vente"),
                    pk=facture_id,
                )

                if facture.vente.statut != "VALIDEE":
                    return Response(
                        {"detail": "Seules les ventes validées peuvent être encaissées."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                total_encaisse = (
                    Encaissement.objects.filter(facture=facture).aggregate(
                        total=Sum("montant")
                    )["total"]
                    or Decimal("0.00")
                )
                total_rembourse = (
                    Remboursement.objects.filter(
                        encaissement__facture=facture,
                        statut=Remboursement.EXECUTE,
                    ).aggregate(total=Sum("montant"))["total"]
                    or Decimal("0.00")
                )

                solde_restant = facture.total - total_encaisse + total_rembourse

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
                    idempotency_key=idempotency_key,
                )
        except IntegrityError:
            existing = Encaissement.objects.filter(
                idempotency_key=idempotency_key
            ).first()
            if existing is None:
                raise
            return self._idempotent_response(
                existing,
                facture_id,
                montant,
                mode_paiement,
            )

        output_serializer = EncaissementSerializer(
            encaissement,
            context=self.get_serializer_context(),
        )

        return Response(
            output_serializer.data,
            status=status.HTTP_201_CREATED,
        )

    def _idempotent_response(
        self,
        existing,
        facture_id,
        montant,
        mode_paiement,
    ):
        if (
            existing.encaisse_par_id != self.request.user.pk
            or existing.facture_id != facture_id
            or existing.montant != montant
            or existing.mode_paiement != mode_paiement
        ):
            return Response(
                {"detail": "Cette clé a déjà été utilisée pour un autre encaissement."},
                status=status.HTTP_409_CONFLICT,
            )
        serializer = EncaissementSerializer(
            existing,
            context=self.get_serializer_context(),
        )
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["get"])
    def recu(self, request, pk=None):
        encaissement = self.get_object()
        paiements_anterieurs = Encaissement.objects.filter(
            facture=encaissement.facture,
        ).filter(
            Q(date_encaissement__lt=encaissement.date_encaissement)
            | Q(
                date_encaissement=encaissement.date_encaissement,
                id__lte=encaissement.id,
            )
        )
        montant_paye = (
            paiements_anterieurs.aggregate(total=Sum("montant"))["total"]
            or Decimal("0.00")
        )
        remboursements_anterieurs = Remboursement.objects.filter(
            encaissement__facture=encaissement.facture,
            statut=Remboursement.EXECUTE,
            date_execution__lte=encaissement.date_encaissement,
        ).aggregate(total=Sum("montant"))["total"] or Decimal("0.00")
        solde = max(
            encaissement.facture.total - montant_paye + remboursements_anterieurs,
            Decimal("0.00"),
        )

        store, _created = ConfigurationMagasin.objects.get_or_create(pk=1)
        logo_url = None
        if store.logo:
            logo_url = request.build_absolute_uri(store.logo.url)

        return Response({
            "encaissement": EncaissementSerializer(
                encaissement,
                context=self.get_serializer_context(),
            ).data,
            "solde_restant_apres": str(solde),
            "magasin": {
                "nom_magasin": store.nom_magasin,
                "logo": logo_url,
                "adresse": store.adresse,
                "telephone": store.telephone,
                "email": store.email,
                "pied_de_page": store.pied_de_page,
            },
        })


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
            ),
            total_rembourse=Coalesce(
                Subquery(
                    Remboursement.objects.filter(
                        encaissement__facture=OuterRef("pk"),
                        statut=Remboursement.EXECUTE,
                    )
                    .values("encaissement__facture")
                    .annotate(total=Sum("montant"))
                    .values("total")[:1]
                ),
                Value(
                    Decimal("0.00"),
                    output_field=DecimalField(
                        max_digits=14,
                        decimal_places=2,
                    ),
                ),
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
                            F("quantite") * F("prix_unitaire"),
                            output_field=DecimalField(
                                max_digits=14,
                                decimal_places=2,
                            ),
                        )
                    )
                    .values("total")[:1]
                ),
                Value(
                    Decimal("0.00"),
                    output_field=DecimalField(
                        max_digits=14,
                        decimal_places=2,
                    ),
                ),
            ),
        )
    )


class RemboursementViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    GenericViewSet,
):
    queryset = Remboursement.objects.select_related(
        "encaissement",
        "encaissement__facture",
        "encaissement__facture__vente",
        "encaissement__facture__vente__client",
        "demande_par",
        "decide_par",
    )

    def get_permissions(self):
        if self.action in {"approuver", "refuser"}:
            return [IsAdministrator()]
        return [CaissePermission()]

    def get_serializer_class(self):
        if self.action == "create":
            return RemboursementCreateSerializer
        return RemboursementSerializer

    def create(self, request, *args, **kwargs):
        input_serializer = self.get_serializer(data=request.data)
        input_serializer.is_valid(raise_exception=True)
        payment_id = input_serializer.validated_data["encaissement_id"]
        amount = input_serializer.validated_data["montant"]
        motif = input_serializer.validated_data["motif"]
        requested_mode = input_serializer.validated_data.get("mode_remboursement")
        raw_key = request.headers.get("Idempotency-Key")
        if not raw_key:
            raise ValidationError({
                "idempotency_key": "L'en-tête Idempotency-Key est obligatoire."
            })
        try:
            idempotency_key = UUID(raw_key)
        except (ValueError, TypeError, AttributeError) as error:
            raise ValidationError({
                "idempotency_key": "L'en-tête Idempotency-Key doit contenir un UUID."
            }) from error

        existing = Remboursement.objects.filter(
            idempotency_key=idempotency_key
        ).first()
        if existing is not None:
            return self._idempotent_response(
                existing,
                payment_id,
                amount,
                motif,
                requested_mode,
            )

        try:
            with transaction.atomic():
                payment = get_object_or_404(
                    Encaissement.objects.select_for_update(),
                    pk=payment_id,
                )
                existing = Remboursement.objects.filter(
                    idempotency_key=idempotency_key
                ).first()
                if existing is not None:
                    return self._idempotent_response(
                        existing,
                        payment_id,
                        amount,
                        motif,
                        requested_mode,
                    )

                reserved = (
                    Remboursement.objects.filter(encaissement=payment)
                    .exclude(statut=Remboursement.REFUSE)
                    .aggregate(total=Sum("montant"))["total"]
                    or Decimal("0.00")
                )
                if amount + reserved > payment.montant:
                    return Response(
                        {
                            "detail": (
                                "Le montant demandé dépasse la part encore "
                                "remboursable de cet encaissement."
                            ),
                            "montant_remboursable": str(payment.montant - reserved),
                        },
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                refund = Remboursement.objects.create(
                    encaissement=payment,
                    montant=amount,
                    motif=motif,
                    mode_remboursement=(
                        requested_mode or payment.mode_paiement
                    ),
                    demande_par=request.user,
                    idempotency_key=idempotency_key,
                )
        except IntegrityError:
            existing = Remboursement.objects.filter(
                idempotency_key=idempotency_key
            ).first()
            if existing is None:
                raise
            return self._idempotent_response(
                existing,
                payment_id,
                amount,
                motif,
                requested_mode,
            )

        return Response(
            RemboursementSerializer(
                refund,
                context=self.get_serializer_context(),
            ).data,
            status=status.HTTP_201_CREATED,
        )

    def _idempotent_response(
        self,
        existing,
        payment_id,
        amount,
        motif,
        requested_mode,
    ):
        if (
            existing.demande_par_id != self.request.user.pk
            or existing.encaissement_id != payment_id
            or existing.montant != amount
            or existing.motif != motif
            or (
                requested_mode is not None
                and existing.mode_remboursement != requested_mode
            )
        ):
            return Response(
                {"detail": "Cette clé a déjà été utilisée pour un autre remboursement."},
                status=status.HTTP_409_CONFLICT,
            )
        return Response(
            RemboursementSerializer(
                existing,
                context=self.get_serializer_context(),
            ).data,
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post"])
    def approuver(self, request, pk=None):
        with transaction.atomic():
            refund = get_object_or_404(
                Remboursement.objects.select_for_update(),
                pk=pk,
            )
            if refund.statut in {
                Remboursement.AUTORISE,
                Remboursement.EXECUTE,
            }:
                return Response(RemboursementSerializer(refund).data)
            if refund.statut != Remboursement.EN_ATTENTE:
                return Response(
                    {"detail": "Seul un remboursement en attente peut être approuvé."},
                    status=status.HTTP_409_CONFLICT,
                )

            payment = Encaissement.objects.select_for_update().get(
                pk=refund.encaissement_id
            )
            already_refunded = (
                Remboursement.objects.filter(
                    encaissement=payment,
                    statut__in=[
                        Remboursement.AUTORISE,
                        Remboursement.EXECUTE,
                    ],
                )
                .exclude(pk=refund.pk)
                .aggregate(total=Sum("montant"))["total"]
                or Decimal("0.00")
            )
            if already_refunded + refund.montant > payment.montant:
                return Response(
                    {"detail": "Le montant dépasse le solde remboursable."},
                    status=status.HTTP_409_CONFLICT,
                )

            refund.statut = Remboursement.AUTORISE
            refund.decide_par = request.user
            refund.date_decision = timezone.now()
            refund.save(
                update_fields=["statut", "decide_par", "date_decision"]
            )

        return Response(
            RemboursementSerializer(
                refund,
                context=self.get_serializer_context(),
            ).data
        )

    @action(detail=True, methods=["post"])
    def executer(self, request, pk=None):
        reference_execution = str(
            request.data.get("reference_execution", "")
        ).strip()
        if not reference_execution or len(reference_execution) > 100:
            raise ValidationError({
                "reference_execution": (
                    "Indique la référence du justificatif d'exécution "
                    "(100 caractères maximum)."
                )
            })

        with transaction.atomic():
            refund = get_object_or_404(
                Remboursement.objects.select_for_update(),
                pk=pk,
            )
            if refund.statut == Remboursement.EXECUTE:
                return Response(
                    RemboursementSerializer(
                        refund,
                        context=self.get_serializer_context(),
                    ).data
                )
            if refund.statut != Remboursement.AUTORISE:
                return Response(
                    {"detail": "Seul un remboursement autorisé peut être exécuté."},
                    status=status.HTTP_409_CONFLICT,
                )

            cash_day = lock_cash_day()
            if cash_day.date_cloture is not None:
                return Response(
                    {"detail": "La caisse de cette journée est déjà clôturée."},
                    status=status.HTTP_409_CONFLICT,
                )

            refund.statut = Remboursement.EXECUTE
            refund.reference_execution = reference_execution
            refund.execute_par = request.user
            refund.date_execution = timezone.now()
            refund.save(update_fields=[
                "statut",
                "reference_execution",
                "execute_par",
                "date_execution",
            ])

        return Response(
            RemboursementSerializer(
                refund,
                context=self.get_serializer_context(),
            ).data
        )

    @action(detail=True, methods=["post"])
    def refuser(self, request, pk=None):
        with transaction.atomic():
            refund = get_object_or_404(
                Remboursement.objects.select_for_update(),
                pk=pk,
            )
            if refund.statut == Remboursement.REFUSE:
                return Response(RemboursementSerializer(refund).data)
            if refund.statut != Remboursement.EN_ATTENTE:
                return Response(
                    {"detail": "Un remboursement autorisé ne peut pas être refusé."},
                    status=status.HTTP_409_CONFLICT,
                )
            refund.statut = Remboursement.REFUSE
            refund.decide_par = request.user
            refund.date_decision = timezone.now()
            refund.save(
                update_fields=["statut", "decide_par", "date_decision"]
            )

        return Response(
            RemboursementSerializer(
                refund,
                context=self.get_serializer_context(),
            ).data
        )


class ClotureCaisseViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    GenericViewSet,
):
    queryset = ClotureCaisse.objects.select_related("cloturee_par").prefetch_related(
        "lignes"
    )
    permission_classes = [CaissePermission]

    def get_serializer_class(self):
        if self.action == "create":
            return ClotureCaisseCreateSerializer
        return ClotureCaisseSerializer

    def list(self, request, *args, **kwargs):
        ClotureCaisse.objects.get_or_create(date_jour=timezone.localdate())
        return super().list(request, *args, **kwargs)

    @action(detail=False, methods=["get"])
    def apercu(self, request):
        with transaction.atomic():
            cash_day = lock_cash_day()
            if cash_day.date_cloture is not None:
                details = ClotureCaisseLigneSerializer(
                    cash_day.lignes.all(),
                    many=True,
                ).data
            else:
                totals = cash_amounts_for_day(cash_day.date_jour)
                labels = dict(Encaissement.MODES_PAIEMENT)
                details = [
                    {
                        "mode_paiement": mode,
                        "mode_paiement_libelle": labels[mode],
                        **{
                            field: str(amount)
                            for field, amount in values.items()
                        },
                        "montant_compte": None,
                        "ecart": None,
                    }
                    for mode, values in totals.items()
                ]

        return Response({
            "date_jour": cash_day.date_jour,
            "date_cloture": cash_day.date_cloture,
            "cloturee": cash_day.date_cloture is not None,
            "lignes": details,
        })

    def create(self, request, *args, **kwargs):
        input_serializer = self.get_serializer(data=request.data)
        input_serializer.is_valid(raise_exception=True)
        counts = input_serializer.validated_data.get("comptage", {})

        with transaction.atomic():
            cash_day = lock_cash_day()
            if cash_day.date_cloture is not None:
                return Response(
                    {"detail": "La caisse de cette journée est déjà clôturée."},
                    status=status.HTTP_409_CONFLICT,
                )

            totals = cash_amounts_for_day(cash_day.date_jour)
            for mode, amounts in totals.items():
                ClotureCaisseLigne.objects.create(
                    cloture=cash_day,
                    mode_paiement=mode,
                    **amounts,
                    montant_compte=counts.get(mode),
                )

            cash_day.cloturee_par = request.user
            cash_day.date_cloture = timezone.now()
            cash_day.save(update_fields=["cloturee_par", "date_cloture"])

        return Response(
            ClotureCaisseSerializer(
                cash_day,
                context=self.get_serializer_context(),
            ).data,
            status=status.HTTP_201_CREATED,
        )
