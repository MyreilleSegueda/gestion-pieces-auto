from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from rest_framework.test import APIClient

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

    def test_supplier_api_requires_authentication(self):
        response = APIClient().get("/api/fournisseurs/")

        self.assertIn(response.status_code, (401, 403))

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
