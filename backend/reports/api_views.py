from decimal import Decimal

from django.db.models import DecimalField, ExpressionWrapper, F, Sum
from django.utils import timezone
from django.utils.dateparse import parse_date
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import BasePermission
from rest_framework.response import Response

from accounts.role_permissions import has_module_access
from caisse.models import Encaissement, Remboursement
from invoicing.models import Facture
from inventory.models import MouvementStock, PieceDetachee
from sales.models import LigneRetourVente, LigneVente, RetourVente, Vente


class ReportsReaderPermission(BasePermission):
    def has_permission(self, request, view):
        return has_module_access(request.user, "rapports")


@api_view(["GET"])
@permission_classes([ReportsReaderPermission])
def tableau_de_bord(request):
    start_raw = request.query_params.get("date_debut")
    end_raw = request.query_params.get("date_fin")
    start_date = parse_date(start_raw) if start_raw else None
    end_date = parse_date(end_raw) if end_raw else None

    if start_raw and start_date is None:
        return Response({"date_debut": "Format attendu : AAAA-MM-JJ."}, status=400)
    if end_raw and end_date is None:
        return Response({"date_fin": "Format attendu : AAAA-MM-JJ."}, status=400)
    if start_date and end_date and start_date > end_date:
        return Response(
            {"detail": "La date de début doit précéder la date de fin."},
            status=400,
        )

    valid_sales = Vente.objects.filter(statut="VALIDEE")
    if start_date:
        valid_sales = valid_sales.filter(date_validation__date__gte=start_date)
    if end_date:
        valid_sales = valid_sales.filter(date_validation__date__lte=end_date)

    line_total = ExpressionWrapper(
        F("quantite") * F("prix_unitaire"),
        output_field=DecimalField(max_digits=24, decimal_places=2),
    )
    sales_total = LigneVente.objects.filter(vente__in=valid_sales).aggregate(
        total=Sum(line_total)
    )["total"] or Decimal("0.00")

    payments = Encaissement.objects.all()
    refunds = Remboursement.objects.filter(
        statut=Remboursement.EXECUTE,
    )
    if start_date:
        payments = payments.filter(date_encaissement__date__gte=start_date)
        refunds = refunds.filter(date_execution__date__gte=start_date)
    if end_date:
        payments = payments.filter(date_encaissement__date__lte=end_date)
        refunds = refunds.filter(date_execution__date__lte=end_date)

    payment_totals = {
        mode: Decimal("0.00")
        for mode, _label in Encaissement.MODES_PAIEMENT
    }
    for row in payments.values("mode_paiement").annotate(total=Sum("montant")):
        payment_totals[row["mode_paiement"]] = row["total"]

    refund_totals = {
        mode: Decimal("0.00")
        for mode, _label in Encaissement.MODES_PAIEMENT
    }
    for row in refunds.values("mode_remboursement").annotate(total=Sum("montant")):
        refund_totals[row["mode_remboursement"]] = row["total"]

    invoice_query = Facture.objects.filter(vente__statut="VALIDEE").prefetch_related(
        "vente__lignes"
    )
    if start_date:
        invoice_query = invoice_query.filter(date_emission__date__gte=start_date)
    if end_date:
        invoice_query = invoice_query.filter(date_emission__date__lte=end_date)

    invoice_payments = {
        row["facture_id"]: row["total"]
        for row in Encaissement.objects.filter(
            facture__in=invoice_query
        ).values("facture_id").annotate(total=Sum("montant"))
    }
    invoice_refunds = {
        row["encaissement__facture_id"]: row["total"]
        for row in Remboursement.objects.filter(
            statut=Remboursement.EXECUTE,
            encaissement__facture__in=invoice_query,
        ).values("encaissement__facture_id").annotate(total=Sum("montant"))
    }
    return_line_total = ExpressionWrapper(
        F("quantite") * F("prix_unitaire"),
        output_field=DecimalField(max_digits=24, decimal_places=2),
    )
    invoice_credits = {
        row["retour__vente__facture__id"]: row["total"]
        for row in LigneRetourVente.objects.filter(
            retour__statut=RetourVente.AUTORISE,
            retour__vente__facture__in=invoice_query,
        )
        .values("retour__vente__facture__id")
        .annotate(total=Sum(return_line_total))
    }
    outstanding = sum(
        (
            max(
                invoice.total
                - invoice_credits.get(invoice.pk, Decimal("0.00"))
                - invoice_payments.get(invoice.pk, Decimal("0.00"))
                + invoice_refunds.get(invoice.pk, Decimal("0.00")),
                Decimal("0.00"),
            )
            for invoice in invoice_query
        ),
        start=Decimal("0.00"),
    )

    recent_movements = MouvementStock.objects.select_related(
        "piece", "utilisateur"
    )[:10]

    return Response({
        "date_debut": start_date,
        "date_fin": end_date,
        "references_actives": PieceDetachee.objects.filter(actif=True).count(),
        "stock_faible": PieceDetachee.objects.filter(
            actif=True,
            quantite_stock__gt=0,
            quantite_stock__lte=F("seuil_minimal"),
        ).count(),
        "ruptures": PieceDetachee.objects.filter(
            actif=True,
            quantite_stock=0,
        ).count(),
        "ventes_validees": valid_sales.count(),
        "chiffre_affaires": f"{sales_total:.2f}",
        "montants_encaisse_brut": f"{sum(payment_totals.values()):.2f}",
        "remboursements_executes": f"{sum(refund_totals.values()):.2f}",
        "montant_encaisse_net": (
            f"{sum(payment_totals.values()) - sum(refund_totals.values()):.2f}"
        ),
        "impayes": f"{outstanding:.2f}",
        "encaissements_par_mode": {
            mode: {
                "encaisse_brut": f"{payment_totals[mode]:.2f}",
                "rembourse": f"{refund_totals[mode]:.2f}",
                "net": f"{payment_totals[mode] - refund_totals[mode]:.2f}",
            }
            for mode, _label in Encaissement.MODES_PAIEMENT
        },
        "mouvements_recents": [
            {
                "id": movement.id,
                "date": movement.date_mouvement,
                "piece_reference": movement.piece.reference,
                "type": movement.type_mouvement,
                "quantite": movement.quantite,
                "motif": movement.motif,
                "utilisateur": (
                    movement.utilisateur.get_full_name()
                    or movement.utilisateur.username
                    if movement.utilisateur
                    else "Non renseigné"
                ),
            }
            for movement in recent_movements
        ],
    })
