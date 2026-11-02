from io import BytesIO

from decimal import Decimal

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.utils import timezone
from openpyxl import load_workbook
from rest_framework.test import APIClient

from caisse.models import Encaissement, Remboursement
from inventory.models import Categorie, MouvementStock, PieceDetachee
from invoicing.models import Facture
from sales.models import LigneVente, Vente
from store_settings.models import ConfigurationMagasin


class DashboardApiTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="rapport-user",
            password="MotDePasseTest-2026",
        )
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.user.groups.add(Group.objects.create(name="Administrateur"))
        category = Categorie.objects.create(nom="Éclairage")
        self.piece = PieceDetachee.objects.create(
            reference="ECL-001",
            designation="Ampoule",
            categorie=category,
            prix_achat="5.00",
            prix_vente="10.00",
            quantite_stock=1,
            seuil_minimal=2,
        )

    def test_business_timezone_is_configured_for_burkina_faso(self):
        self.assertEqual(settings.TIME_ZONE, "Africa/Ouagadougou")
        self.assertEqual(timezone.get_current_timezone_name(), "Africa/Ouagadougou")

    def test_staff_without_reports_role_cannot_read_dashboard_or_export(self):
        user = get_user_model().objects.create_user(
            username="staff-without-reports-role",
            password="MotDePasseTest-2026",
            is_staff=True,
        )
        client = APIClient()
        client.force_authenticate(user)

        self.assertEqual(
            client.get("/api/rapports/tableau-de-bord/").status_code,
            403,
        )
        self.assertEqual(
            client.get("/api/rapports/export/indicateurs/").status_code,
            403,
        )

    def test_dashboard_returns_inventory_and_validated_sales(self):
        sale = Vente.objects.create(
            statut="VALIDEE",
            creee_par=self.user,
            validee_par=self.user,
            date_validation=timezone.now(),
        )
        LigneVente.objects.create(
            vente=sale,
            piece=self.piece,
            reference_piece=self.piece.reference,
            designation=self.piece.designation,
            quantite=3,
            prix_unitaire=Decimal("10.00"),
        )
        Vente.objects.create(statut="BROUILLON", creee_par=self.user)

        response = self.client.get("/api/rapports/tableau-de-bord/")

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.data["references_actives"], 1)
        self.assertEqual(response.data["stock_faible"], 1)
        self.assertEqual(response.data["ventes_validees"], 1)
        self.assertEqual(response.data["chiffre_affaires"], "30.00")

    def test_dashboard_rejects_invalid_date_range(self):
        response = self.client.get(
            "/api/rapports/tableau-de-bord/?date_debut=2026-10-30&date_fin=2026-10-01"
        )

        self.assertEqual(response.status_code, 400)

    def test_dashboard_refresh_includes_new_stock_movement(self):
        first_response = self.client.get("/api/rapports/tableau-de-bord/")
        self.assertEqual(first_response.data["stock_faible"], 1)

        MouvementStock.objects.create(
            piece=self.piece,
            type_mouvement="SORTIE",
            quantite=1,
            motif="Sortie de test",
            utilisateur=self.user,
        )

        refreshed_response = self.client.get("/api/rapports/tableau-de-bord/")

        self.assertEqual(refreshed_response.status_code, 200)
        self.assertEqual(refreshed_response.data["ruptures"], 1)
        self.assertEqual(len(refreshed_response.data["mouvements_recents"]), 1)

    def test_dashboard_refresh_includes_new_validated_sale(self):
        vendor_group, _ = Group.objects.get_or_create(name="Vendeur")
        self.user.groups.add(vendor_group)
        sale_client = APIClient()
        sale_client.force_authenticate(self.user)

        created = sale_client.post(
            "/api/ventes/",
            {"client": None, "lignes": [{"piece": self.piece.pk, "quantite": 1}]},
            format="json",
        )
        self.assertEqual(created.status_code, 201, created.data)
        validated = sale_client.post(f"/api/ventes/{created.data['id']}/valider/")
        self.assertEqual(validated.status_code, 200, validated.data)

        response = self.client.get("/api/rapports/tableau-de-bord/")

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.data["ventes_validees"], 1)
        self.assertEqual(response.data["chiffre_affaires"], "10.00")

    def test_dashboard_requires_authentication(self):
        response = APIClient().get("/api/rapports/tableau-de-bord/")

        self.assertIn(response.status_code, (401, 403))

    def test_dashboard_separates_sales_receipts_refunds_and_unpaid_balances(self):
        sale = Vente.objects.create(
            statut="VALIDEE",
            creee_par=self.user,
            validee_par=self.user,
            date_validation=timezone.now(),
        )
        LigneVente.objects.create(
            vente=sale,
            piece=self.piece,
            reference_piece=self.piece.reference,
            designation=self.piece.designation,
            quantite=3,
            prix_unitaire=Decimal("10.00"),
        )
        invoice = Facture.objects.create(vente=sale, emise_par=self.user)
        payment = Encaissement.objects.create(
            facture=invoice,
            montant=Decimal("20.00"),
            mode_paiement="ESPECES",
            encaisse_par=self.user,
        )
        Remboursement.objects.create(
            encaissement=payment,
            montant=Decimal("5.00"),
            motif="Erreur de paiement",
            statut=Remboursement.EXECUTE,
            mode_remboursement="ESPECES",
            demande_par=self.user,
            decide_par=self.user,
            date_decision=timezone.now(),
            execute_par=self.user,
            date_execution=timezone.now(),
            reference_execution="TEST-REFUND-EXEC-001",
        )

        response = self.client.get("/api/rapports/tableau-de-bord/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["chiffre_affaires"], "30.00")
        self.assertEqual(response.data["montants_encaisse_brut"], "20.00")
        self.assertEqual(response.data["remboursements_executes"], "5.00")
        self.assertEqual(response.data["montant_encaisse_net"], "15.00")
        self.assertEqual(response.data["impayes"], "15.00")
        self.assertEqual(
            response.data["encaissements_par_mode"]["ESPECES"]["net"],
            "15.00",
        )

    def test_xlsx_stock_export_is_a_real_filtered_spreadsheet(self):
        second_piece = PieceDetachee.objects.create(
            reference="ECL-002",
            designation="Ampoule secondaire",
            categorie=self.piece.categorie,
            prix_achat="3.00",
            prix_vente="8.00",
            quantite_stock=5,
        )
        response = self.client.get(
            f"/api/rapports/export/stock/?export_format=xlsx&piece={self.piece.pk}"
        )

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(
            response["Content-Type"],
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        workbook = load_workbook(BytesIO(response.content), read_only=True)
        rows = list(workbook.active.values)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[1][0], self.piece.reference)
        self.assertNotEqual(rows[1][0], second_piece.reference)

    def test_pdf_export_is_a_real_branded_pdf_and_unauthorized_cash_export_is_denied(self):
        ConfigurationMagasin.objects.create(
            nom_magasin="Garage de test",
            adresse="Ouagadougou",
            pied_de_page="Merci de votre confiance",
        )
        response = self.client.get("/api/rapports/export/indicateurs/?export_format=pdf")

        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertTrue(response.content.startswith(b"%PDF-"))
        self.assertIn(b"attachment;", response["Content-Disposition"].encode())

        seller = get_user_model().objects.create_user(
            username="export-seller",
            password="test-password",
        )
        seller.groups.add(Group.objects.create(name="Vendeur"))
        seller_client = APIClient()
        seller_client.force_authenticate(seller)
        denied = seller_client.get("/api/rapports/export/encaissements/?export_format=xlsx")
        self.assertEqual(denied.status_code, 403)

    def test_movements_export_applies_piece_user_and_movement_type_filters(self):
        other_piece = PieceDetachee.objects.create(
            reference="ECL-003",
            designation="Lampe",
            categorie=self.piece.categorie,
            prix_achat="4.00",
            prix_vente="9.00",
            quantite_stock=2,
        )
        MouvementStock.objects.create(
            piece=self.piece,
            type_mouvement="ENTREE",
            quantite=2,
            prix_unitaire=Decimal("5.00"),
            motif="Réception filtrée",
            utilisateur=self.user,
        )
        MouvementStock.objects.create(
            piece=other_piece,
            type_mouvement="SORTIE",
            quantite=1,
            prix_unitaire=Decimal("5.00"),
            motif="Sortie ignorée",
            utilisateur=self.user,
        )

        response = self.client.get(
            "/api/rapports/export/mouvements/?export_format=xlsx"
            f"&piece={self.piece.pk}&utilisateur={self.user.pk}"
            "&type_mouvement=ENTREE"
        )

        workbook = load_workbook(BytesIO(response.content), read_only=True)
        rows = list(workbook.active.values)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(rows), 2)
        self.assertIn("Réception filtrée", rows[1])
