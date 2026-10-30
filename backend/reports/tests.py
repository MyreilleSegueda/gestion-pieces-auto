from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from inventory.models import Categorie, MouvementStock, PieceDetachee
from sales.models import LigneVente, Vente


class DashboardApiTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="rapport-user",
            password="MotDePasseTest-2026",
        )
        self.client = APIClient()
        self.client.force_authenticate(self.user)
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

        self.assertEqual(response.status_code, 200)
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

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["ventes_validees"], 1)
        self.assertEqual(response.data["chiffre_affaires"], "10.00")

    def test_dashboard_requires_authentication(self):
        response = APIClient().get("/api/rapports/tableau-de-bord/")

        self.assertIn(response.status_code, (401, 403))
