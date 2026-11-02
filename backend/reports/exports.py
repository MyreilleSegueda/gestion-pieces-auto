from decimal import Decimal
from io import BytesIO
from xml.sax.saxutils import escape

from django.db.models import DecimalField, ExpressionWrapper, F, Sum
from django.http import HttpResponse
from django.utils import timezone
from django.utils.dateparse import parse_date
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Table, TableStyle
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from accounts.role_permissions import has_module_access
from caisse.models import Encaissement, Remboursement
from fournisseurs.models import AchatFournisseur
from inventory.models import MouvementStock, PieceDetachee
from invoicing.models import Facture
from sales.models import LigneRetourVente, LigneVente, RetourVente, Vente
from store_settings.models import ConfigurationMagasin


EXPORTS = {
    "factures": ("Factures", "factures"),
    "encaissements": ("Encaissements et reçus", "caisse"),
    "remboursements": ("Remboursements", "caisse"),
    "stock": ("État du stock", "stock"),
    "mouvements": ("Mouvements de stock", "stock"),
    "ventes": ("Ventes validées", "ventes"),
    "retours": ("Retours et annulations", "ventes"),
    "achats-fournisseurs": ("Achats fournisseurs", "fournisseurs"),
    "indicateurs": ("Indicateurs", "rapports"),
}
MAX_EXPORT_ROWS = 50000


def _business_datetime(value):
    if value is None:
        return ""
    return timezone.localtime(value).strftime("%Y-%m-%d %H:%M:%S")


def _query_filters(request):
    params = request.query_params
    raw_start = params.get("date_debut")
    raw_end = params.get("date_fin")
    start = parse_date(raw_start) if raw_start else None
    end = parse_date(raw_end) if raw_end else None
    if raw_start and start is None:
        raise ValidationError({"date_debut": "Format attendu : AAAA-MM-JJ."})
    if raw_end and end is None:
        raise ValidationError({"date_fin": "Format attendu : AAAA-MM-JJ."})
    if start and end and start > end:
        raise ValidationError({"detail": "La date de début doit précéder la date de fin."})

    piece_id = params.get("piece")
    if piece_id and not piece_id.isdigit():
        raise ValidationError({"piece": "L'identifiant de la pièce doit être numérique."})
    user_id = params.get("utilisateur")
    if user_id and not user_id.isdigit():
        raise ValidationError({"utilisateur": "L'identifiant de l'utilisateur doit être numérique."})

    return {
        "start": start,
        "end": end,
        "piece": int(piece_id) if piece_id else None,
        "user": int(user_id) if user_id else None,
        "movement_type": params.get("type_mouvement"),
    }


def _apply_date_range(queryset, field, filters):
    if filters["start"]:
        queryset = queryset.filter(**{f"{field}__date__gte": filters["start"]})
    if filters["end"]:
        queryset = queryset.filter(**{f"{field}__date__lte": filters["end"]})
    return queryset


def _rows_for_export(export_type, filters):
    if export_type == "stock":
        pieces = PieceDetachee.objects.select_related("categorie").all()
        if filters["piece"]:
            pieces = pieces.filter(pk=filters["piece"])
        return [
            ["Référence", "Désignation", "Catégorie", "Marque", "Stock", "Seuil", "Prix achat", "Prix vente", "Emplacement", "Actif"],
            *[
                [
                    item.reference,
                    item.designation,
                    item.categorie.nom,
                    item.marque,
                    item.quantite_stock,
                    item.seuil_minimal,
                    str(item.prix_achat),
                    str(item.prix_vente),
                    item.emplacement,
                    "Oui" if item.actif else "Non",
                ]
                for item in pieces
            ],
        ]

    if export_type == "mouvements":
        movements = MouvementStock.objects.select_related("piece", "utilisateur")
        movements = _apply_date_range(movements, "date_mouvement", filters)
        if filters["piece"]:
            movements = movements.filter(piece_id=filters["piece"])
        if filters["user"]:
            movements = movements.filter(utilisateur_id=filters["user"])
        if filters["movement_type"]:
            valid_types = dict(MouvementStock.TYPES_MOUVEMENT)
            if filters["movement_type"] not in valid_types:
                raise ValidationError({"type_mouvement": "Type de mouvement inconnu."})
            movements = movements.filter(type_mouvement=filters["movement_type"])
        return [
            ["Date", "Pièce", "Type", "Quantité", "Prix unitaire", "Motif", "Document", "Utilisateur"],
            *[
                [
                    _business_datetime(item.date_mouvement),
                    item.piece.reference,
                    item.get_type_mouvement_display(),
                    item.quantite,
                    str(item.prix_unitaire),
                    item.motif,
                    item.reference_document,
                    (
                        item.utilisateur.get_full_name() or item.utilisateur.username
                        if item.utilisateur else "Non renseigné"
                    ),
                ]
                for item in movements
            ],
        ]

    if export_type == "ventes":
        sales = Vente.objects.filter(statut__in=["VALIDEE", "ANNULEE"]).select_related(
            "client", "validee_par"
        ).prefetch_related("lignes")
        sales = _apply_date_range(sales, "date_validation", filters)
        if filters["piece"]:
            sales = sales.filter(lignes__piece_id=filters["piece"]).distinct()
        if filters["user"]:
            sales = sales.filter(validee_par_id=filters["user"])
        rows = [["Vente", "Date validation", "Statut", "Client", "Pièce", "Désignation", "Quantité", "Prix unitaire", "Total ligne", "Validée par"]]
        for sale in sales:
            for line in sale.lignes.all():
                rows.append([
                    sale.reference,
                    _business_datetime(sale.date_validation),
                    sale.get_statut_display(),
                    sale.client.nom if sale.client else "Vente comptant",
                    line.reference_piece,
                    line.designation,
                    line.quantite,
                    str(line.prix_unitaire),
                    str(line.total),
                    (
                        sale.validee_par.get_full_name() or sale.validee_par.username
                        if sale.validee_par else "Non renseigné"
                    ),
                ])
        return rows

    if export_type == "factures":
        invoices = Facture.objects.filter(
            vente__statut__in=["VALIDEE", "ANNULEE"]
        ).select_related("vente__client", "emise_par").prefetch_related(
            "vente__lignes",
            "encaissements__remboursements",
        )
        invoices = _apply_date_range(invoices, "date_emission", filters)
        if filters["piece"]:
            invoices = invoices.filter(vente__lignes__piece_id=filters["piece"]).distinct()
        if filters["user"]:
            invoices = invoices.filter(emise_par_id=filters["user"])
        rows = [["Facture", "Vente", "Date émission", "Client", "Statut", "Pièce", "Désignation", "Quantité", "Prix unitaire", "Total ligne", "Total facture", "Avoirs", "Encaissé brut", "Remboursé exécuté", "Solde restant"]]
        for invoice in invoices:
            sale = invoice.vente
            line_items = list(sale.lignes.all())
            total = sum((line.total for line in line_items), start=Decimal("0.00"))
            paid = sum((payment.montant for payment in invoice.encaissements.all()), start=Decimal("0.00"))
            refunded = sum(
                (
                    refund.montant
                    for payment in invoice.encaissements.all()
                    for refund in payment.remboursements.all()
                    if refund.statut == Remboursement.EXECUTE
                ),
                start=Decimal("0.00"),
            )
            credits = LigneRetourVente.objects.filter(
                retour__vente=sale,
                retour__statut=RetourVente.AUTORISE,
            ).aggregate(
                total=Sum(
                    ExpressionWrapper(
                        F("quantite") * F("prix_unitaire"),
                        output_field=DecimalField(max_digits=24, decimal_places=2),
                    )
                )
            )["total"] or Decimal("0.00")
            outstanding = max(total - credits - paid + refunded, Decimal("0.00"))
            for line in line_items:
                rows.append([
                    invoice.reference,
                    sale.reference,
                    _business_datetime(invoice.date_emission),
                    sale.client.nom if sale.client else "Vente comptant",
                    "Annulée" if sale.statut == "ANNULEE" else "Émise",
                    line.reference_piece,
                    line.designation,
                    line.quantite,
                    str(line.prix_unitaire),
                    str(line.total),
                    str(total),
                    str(credits),
                    str(paid),
                    str(refunded),
                    str(outstanding),
                ])
        return rows

    if export_type == "encaissements":
        payments = Encaissement.objects.select_related(
            "facture__vente__client",
            "encaisse_par",
        )
        payments = _apply_date_range(payments, "date_encaissement", filters)
        if filters["piece"]:
            payments = payments.filter(facture__vente__lignes__piece_id=filters["piece"]).distinct()
        if filters["user"]:
            payments = payments.filter(encaisse_par_id=filters["user"])
        return [
            ["Reçu", "Facture", "Date", "Client", "Montant", "Mode", "Encaissé par"],
            *[
                [
                    payment.reference,
                    payment.facture.reference,
                    _business_datetime(payment.date_encaissement),
                    payment.facture.vente.client.nom if payment.facture.vente.client else "Vente comptant",
                    str(payment.montant),
                    payment.get_mode_paiement_display(),
                    (
                        payment.encaisse_par.get_full_name() or payment.encaisse_par.username
                        if payment.encaisse_par else "Non renseigné"
                    ),
                ]
                for payment in payments
            ],
        ]

    if export_type == "remboursements":
        refunds = Remboursement.objects.select_related(
            "encaissement__facture__vente__client",
            "demande_par",
            "decide_par",
            "execute_par",
        )
        refunds = _apply_date_range(refunds, "date_demande", filters)
        if filters["piece"]:
            refunds = refunds.filter(
                encaissement__facture__vente__lignes__piece_id=filters["piece"]
            ).distinct()
        if filters["user"]:
            refunds = refunds.filter(demande_par_id=filters["user"])
        return [
            ["Remboursement", "Reçu", "Facture", "Date demande", "Montant", "Mode", "Motif", "Statut", "Référence exécution", "Demandé par", "Décidé par", "Exécuté par", "Date exécution"],
            *[
                [
                    refund.reference,
                    refund.encaissement.reference,
                    refund.encaissement.facture.reference,
                    _business_datetime(refund.date_demande),
                    str(refund.montant),
                    refund.get_mode_remboursement_display(),
                    refund.motif,
                    refund.get_statut_display(),
                    refund.reference_execution,
                    refund.demande_par.get_full_name() or refund.demande_par.username if refund.demande_par else "",
                    refund.decide_par.get_full_name() or refund.decide_par.username if refund.decide_par else "",
                    refund.execute_par.get_full_name() or refund.execute_par.username if refund.execute_par else "",
                    _business_datetime(refund.date_execution),
                ]
                for refund in refunds
            ],
        ]

    if export_type == "retours":
        returns = RetourVente.objects.select_related(
            "vente",
            "demande_par",
            "autorise_par",
        ).prefetch_related("lignes")
        returns = _apply_date_range(returns, "date_demande", filters)
        if filters["piece"]:
            returns = returns.filter(lignes__ligne_vente__piece_id=filters["piece"]).distinct()
        if filters["user"]:
            returns = returns.filter(demande_par_id=filters["user"])
        rows = [["Référence", "Vente", "Type", "Date demande", "Statut", "Motif", "Pièce", "Quantité", "Prix unitaire", "Total retour", "Remise en stock", "Demandé par", "Autorisé par"]]
        for record in returns:
            for line in record.lignes.all():
                rows.append([
                    record.reference,
                    record.vente.reference,
                    record.get_type_operation_display(),
                    _business_datetime(record.date_demande),
                    record.get_statut_display(),
                    record.motif,
                    line.reference_piece,
                    line.quantite,
                    str(line.prix_unitaire),
                    str(line.quantite * line.prix_unitaire),
                    "Oui" if record.remise_en_stock else "Non",
                    record.demande_par.get_full_name() or record.demande_par.username if record.demande_par else "",
                    record.autorise_par.get_full_name() or record.autorise_par.username if record.autorise_par else "",
                ])
        return rows

    if export_type == "achats-fournisseurs":
        purchases = AchatFournisseur.objects.select_related(
            "fournisseur", "cree_par", "recu_par"
        ).prefetch_related("lignes")
        purchases = _apply_date_range(purchases, "date_creation", filters)
        if filters["piece"]:
            purchases = purchases.filter(lignes__piece_id=filters["piece"]).distinct()
        if filters["user"]:
            purchases = purchases.filter(cree_par_id=filters["user"])
        rows = [["Achat", "Fournisseur", "Date création", "Date réception", "Statut", "Pièce", "Désignation", "Quantité", "Prix unitaire", "Total ligne", "Créé par", "Reçu par"]]
        for purchase in purchases:
            for line in purchase.lignes.all():
                rows.append([
                    purchase.reference,
                    purchase.fournisseur.nom,
                    _business_datetime(purchase.date_creation),
                    _business_datetime(purchase.date_reception),
                    purchase.get_statut_display(),
                    line.reference_piece,
                    line.designation,
                    line.quantite,
                    str(line.prix_unitaire),
                    str(line.quantite * line.prix_unitaire),
                    purchase.cree_par.get_full_name() or purchase.cree_par.username if purchase.cree_par else "",
                    purchase.recu_par.get_full_name() or purchase.recu_par.username if purchase.recu_par else "",
                ])
        return rows

    if export_type == "indicateurs":
        sales = Vente.objects.filter(statut="VALIDEE")
        sales = _apply_date_range(sales, "date_validation", filters)
        if filters["piece"]:
            sales = sales.filter(lignes__piece_id=filters["piece"]).distinct()
        if filters["user"]:
            sales = sales.filter(validee_par_id=filters["user"])
        sales_amount = LigneVente.objects.filter(vente__in=sales).aggregate(
            total=Sum(
                ExpressionWrapper(
                    F("quantite") * F("prix_unitaire"),
                    output_field=DecimalField(max_digits=24, decimal_places=2),
                )
            )
        )["total"] or Decimal("0.00")
        payments = Encaissement.objects.all()
        payments = _apply_date_range(payments, "date_encaissement", filters)
        if filters["piece"]:
            payments = payments.filter(facture__vente__lignes__piece_id=filters["piece"]).distinct()
        if filters["user"]:
            payments = payments.filter(encaisse_par_id=filters["user"])
        received = payments.aggregate(total=Sum("montant"))["total"] or Decimal("0.00")
        refunds = Remboursement.objects.filter(statut=Remboursement.EXECUTE)
        refunds = _apply_date_range(refunds, "date_execution", filters)
        if filters["user"]:
            refunds = refunds.filter(execute_par_id=filters["user"])
        refunded = refunds.aggregate(total=Sum("montant"))["total"] or Decimal("0.00")
        return [
            ["Indicateur", "Valeur"],
            ["Ventes validées", sales.count()],
            ["Chiffre d'affaires", str(sales_amount)],
            ["Encaissements bruts", str(received)],
            ["Remboursements exécutés", str(refunded)],
            ["Encaissements nets", str(received - refunded)],
            ["Références actives", PieceDetachee.objects.filter(actif=True).count()],
            ["Stock faible", PieceDetachee.objects.filter(
                actif=True,
                quantite_stock__gt=0,
                quantite_stock__lte=F("seuil_minimal"),
            ).count()],
            ["Ruptures", PieceDetachee.objects.filter(actif=True, quantite_stock=0).count()],
        ]

    raise ValidationError({"type": "Type d'export inconnu."})


def _make_xlsx(title, rows):
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = title[:31]
    for row_index, row in enumerate(rows, start=1):
        for column_index, value in enumerate(row, start=1):
            cell = sheet.cell(row=row_index, column=column_index, value=value)
            if row_index == 1:
                cell.font = Font(bold=True, color="FFFFFF")
                cell.fill = PatternFill("solid", fgColor="243B53")
            elif isinstance(value, str):
                cell.data_type = "s"
            cell.alignment = Alignment(vertical="top", wrap_text=True)
    sheet.freeze_panes = "A2"
    sheet.auto_filter.ref = sheet.dimensions
    for column in sheet.columns:
        letter = column[0].column_letter
        width = min(max(max(len(str(cell.value or "")) for cell in column) + 2, 12), 40)
        sheet.column_dimensions[letter].width = width
    buffer = BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def _make_pdf(title, rows, store):
    buffer = BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        rightMargin=10 * mm,
        leftMargin=10 * mm,
        topMargin=12 * mm,
        bottomMargin=12 * mm,
        title=title,
    )
    story = [
        Paragraph(escape(store.nom_magasin), ParagraphStyle(
            "StoreTitle",
            fontName="Helvetica-Bold",
            fontSize=14,
            leading=17,
            alignment=TA_LEFT,
        )),
        Paragraph(escape(title), ParagraphStyle(
            "ReportTitle",
            fontName="Helvetica",
            fontSize=10,
            leading=13,
        )),
    ]
    contact = " · ".join(filter(None, [store.adresse, store.telephone, store.email]))
    if contact:
        story.append(Paragraph(escape(contact), ParagraphStyle(
            "StoreContact",
            fontName="Helvetica",
            fontSize=8,
            leading=10,
        )))
    table_style = ParagraphStyle(
        "Cell",
        fontName="Helvetica",
        fontSize=6.5,
        leading=8,
        wordWrap="CJK",
    )
    table_data = [
        [Paragraph(f"<b>{escape(str(value))}</b>", table_style) for value in rows[0]]
    ]
    table_data.extend([
        [Paragraph(escape(str(value or "")), table_style) for value in row]
        for row in rows[1:]
    ])
    widths = [(landscape(A4)[0] - 20 * mm) / max(len(rows[0]), 1)] * len(rows[0])
    table = Table(table_data, colWidths=widths, repeatRows=1, splitByRow=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#243B53")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#CBD5E1")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 3),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    story.append(table)
    if store.pied_de_page:
        story.append(Paragraph(escape(store.pied_de_page), table_style))
    document.build(story)
    return buffer.getvalue()


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def export_report(request, export_type):
    if export_type not in EXPORTS:
        return Response({"type": "Type d'export inconnu."}, status=status.HTTP_404_NOT_FOUND)

    title, module = EXPORTS[export_type]
    if not has_module_access(request.user, module):
        return Response(
            {"detail": "Vous n'êtes pas autorisé à exporter ces données."},
            status=status.HTTP_403_FORBIDDEN,
        )

    output_format = request.query_params.get("export_format", "xlsx").lower()
    if output_format not in {"xlsx", "pdf"}:
        return Response({"format": "Format autorisé : xlsx ou pdf."}, status=400)

    try:
        filters = _query_filters(request)
        rows = _rows_for_export(export_type, filters)
    except ValidationError as error:
        return Response(error.detail, status=status.HTTP_400_BAD_REQUEST)
    if len(rows) - 1 > MAX_EXPORT_ROWS:
        return Response(
            {"detail": f"Export trop volumineux (maximum {MAX_EXPORT_ROWS} lignes)."},
            status=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
        )

    if output_format == "xlsx":
        content = _make_xlsx(title, rows)
        content_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    else:
        store = ConfigurationMagasin.objects.first() or ConfigurationMagasin()
        content = _make_pdf(title, rows, store)
        content_type = "application/pdf"
    response = HttpResponse(content, content_type=content_type)
    response["Content-Disposition"] = (
        f'attachment; filename="{export_type}-{timezone.localdate().isoformat()}.{output_format}"'
    )
    response["X-Content-Type-Options"] = "nosniff"
    return response
