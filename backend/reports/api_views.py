from decimal import Decimal

from django.db.models import DecimalField, ExpressionWrapper, F, Sum
from django.utils import timezone
from django.utils.dateparse import parse_date
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from inventory.models import MouvementStock, PieceDetachee
from sales.models import LigneVente, Vente


@api_view(["GET"])
@permission_classes([IsAuthenticated])
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
