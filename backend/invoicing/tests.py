from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from rest_framework.test import APIClient

from clients.models import Client
from inventory.models import Categorie, PieceDetachee
from sales.models import Vente

from .models import Facture


class FactureApiTests(TestCase):
    def setUp(self):
        user = get_user_model().objects.create_user(
            username="vendeur-facture",
            password="MotDePasseTest-2026",
        )
        group = Group.objects.create(name="Vendeur")
        user.groups.add(group)
        category = Categorie.objects.create(nom="Transmission")
        self.piece = PieceDetachee.objects.create(
            reference="TRN-001",
            designation="Courroie",
            categorie=category,
            prix_achat="1000.00",
            prix_vente="2500.00",
            quantite_stock=10,
        )
        self.client = APIClient()
        self.client.force_authenticate(user)

    def create_validated_sale(self):
        response = self.client.post(
            "/api/ventes/",
            {"lignes": [{"piece": self.piece.pk, "quantite": 2}]},
            format="json",
        )
        sale_id = response.data["id"]
        self.client.post(f"/api/ventes/{sale_id}/valider/")
        return Vente.objects.get(pk=sale_id)

    def test_validated_sale_generates_one_read_only_invoice(self):
        sale = self.create_validated_sale()

        invoice = Facture.objects.get(vente=sale)
        response = self.client.get(f"/api/factures/{invoice.pk}/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["vente_reference"], sale.reference)
        self.assertEqual(response.data["total"], "5000.00")
        self.assertEqual(len(response.data["lignes"]), 1)

    def test_invoice_api_requires_authentication(self):
        self.create_validated_sale()

        response = APIClient().get("/api/factures/")

        self.assertIn(response.status_code, (401, 403))

    def test_invoice_cannot_be_created_or_deleted_directly(self):
        sale = self.create_validated_sale()
        invoice = Facture.objects.get(vente=sale)

        create_response = self.client.post(
            "/api/factures/",
            {"vente": sale.pk},
            format="json",
        )
        delete_response = self.client.delete(f"/api/factures/{invoice.pk}/")

        self.assertEqual(create_response.status_code, 405)
        self.assertEqual(delete_response.status_code, 405)
        self.assertTrue(Facture.objects.filter(pk=invoice.pk).exists())
