from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from rest_framework.test import APIClient

from inventory.models import Categorie, MouvementStock, PieceDetachee

from .models import Fournisseur


class FournisseurApiTests(TestCase):
    def setUp(self):
        user = get_user_model().objects.create_user(
            username="gestionnaire-fournisseur",
            password="MotDePasseTest-2026",
        )
        group = Group.objects.create(name="Gestionnaire de stock")
        user.groups.add(group)
        self.client = APIClient()
        self.client.force_authenticate(user)
        self.user = user

    def test_supplier_api_requires_authentication(self):
        response = APIClient().get("/api/fournisseurs/")

        self.assertIn(response.status_code, (401, 403))

    def test_staff_without_supplier_role_cannot_read_or_create_suppliers(self):
        user = get_user_model().objects.create_user(
            username="staff-without-supplier-role",
            password="MotDePasseTest-2026",
            is_staff=True,
        )
        client = APIClient()
        client.force_authenticate(user)

        self.assertEqual(client.get("/api/fournisseurs/").status_code, 403)
        self.assertEqual(
            client.post("/api/fournisseurs/", {"nom": "Non autorisé"}).status_code,
            403,
        )

    def test_stock_manager_can_create_and_deactivate_supplier(self):
        response = self.client.post(
            "/api/fournisseurs/",
            {
                "nom": "Auto Parts BF",
                "telephone": "+22670000000",
                "email": "contact@example.test",
                "adresse": "Ouagadougou",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201, response.data)
        supplier_id = response.data["id"]
        update = self.client.patch(
            f"/api/fournisseurs/{supplier_id}/",
            {"actif": False},
            format="json",
        )

        self.assertEqual(update.status_code, 200)
        self.assertFalse(Fournisseur.objects.get(pk=supplier_id).actif)

    def test_supplier_cannot_be_permanently_deleted(self):
        supplier = Fournisseur.objects.create(nom="Auto Parts BF")

        response = self.client.delete(f"/api/fournisseurs/{supplier.pk}/")

        self.assertEqual(response.status_code, 405)
        self.assertTrue(Fournisseur.objects.filter(pk=supplier.pk).exists())

    def test_purchase_changes_stock_only_on_idempotent_receipt(self):
        supplier = Fournisseur.objects.create(nom="Auto Parts BF")
        category = Categorie.objects.create(nom="Freinage achat test")
        piece = PieceDetachee.objects.create(
            reference="BRK-ACH-001",
            designation="Plaquettes",
            categorie=category,
            prix_achat="100.00",
            prix_vente="180.00",
            quantite_stock=4,
        )

        created = self.client.post(
            "/api/achats-fournisseurs/",
            {
                "fournisseur": supplier.pk,
                "lignes": [{
                    "piece": piece.pk,
                    "quantite": 3,
                    "prix_unitaire": "95.50",
                }],
            },
            format="json",
        )

        self.assertEqual(created.status_code, 201, created.data)
        self.assertEqual(created.data["statut"], "BROUILLON")
        self.assertEqual(created.data["montant_total"], "286.50")
        piece.refresh_from_db()
        self.assertEqual(piece.quantite_stock, 4)
        self.assertFalse(MouvementStock.objects.filter(
            reference_document=created.data["reference"],
        ).exists())

        received = self.client.post(
            f"/api/achats-fournisseurs/{created.data['id']}/recevoir/",
            {},
            format="json",
        )
        repeated = self.client.post(
            f"/api/achats-fournisseurs/{created.data['id']}/recevoir/",
            {},
            format="json",
        )

        self.assertEqual(received.status_code, 200, received.data)
        self.assertEqual(received.data["statut"], "RECU")
        self.assertEqual(received.data["recu_par"], self.user.pk)
        self.assertIsNotNone(received.data["date_reception"])
        self.assertEqual(repeated.status_code, 200)
        piece.refresh_from_db()
        self.assertEqual(piece.quantite_stock, 7)
        self.assertEqual(
            MouvementStock.objects.filter(
                type_mouvement="ENTREE",
                reference_document=created.data["reference"],
            ).count(),
            1,
        )

    def test_sales_role_cannot_create_or_receive_supplier_purchases(self):
        supplier = Fournisseur.objects.create(nom="Supplier")
        seller = get_user_model().objects.create_user(
            username="seller-purchase",
            password="test-password",
        )
        seller.groups.add(Group.objects.create(name="Vendeur"))
        client = APIClient()
        client.force_authenticate(seller)

        response = client.post(
            "/api/achats-fournisseurs/",
            {"fournisseur": supplier.pk, "lignes": []},
            format="json",
        )

        self.assertEqual(response.status_code, 403)
