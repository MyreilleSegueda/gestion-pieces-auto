from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from rest_framework.test import APIClient

from .models import Client


class ClientApiTests(TestCase):
    def setUp(self):
        user = get_user_model().objects.create_user(
            username="vendeur-client",
            password="MotDePasseTest-2026",
        )
        group = Group.objects.create(name="Vendeur")
        user.groups.add(group)
        self.client = APIClient()
        self.client.force_authenticate(user)

    def test_clients_require_authentication(self):
        response = APIClient().get("/api/clients/")

        self.assertIn(response.status_code, (401, 403))

    def test_staff_without_client_role_cannot_read_or_modify_clients(self):
        user = get_user_model().objects.create_user(
            username="staff-without-client-role",
            password="MotDePasseTest-2026",
            is_staff=True,
        )
        client = APIClient()
        client.force_authenticate(user)

        self.assertEqual(client.get("/api/clients/").status_code, 403)
        self.assertEqual(
            client.post("/api/clients/", {"nom": "Non autorisé"}).status_code,
            403,
        )

    def test_vendor_can_create_and_deactivate_client(self):
        response = self.client.post(
            "/api/clients/",
            {
                "nom": "Garage Wendpanga",
                "telephone": "+22670000000",
                "adresse": "Ouagadougou",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201, response.data)
        client_id = response.data["id"]
        update = self.client.patch(
            f"/api/clients/{client_id}/",
            {"actif": False},
            format="json",
        )

        self.assertEqual(update.status_code, 200)
        self.assertFalse(Client.objects.get(pk=client_id).actif)

    def test_client_cannot_be_permanently_deleted(self):
        client = Client.objects.create(nom="Garage Wendpanga")

        response = self.client.delete(f"/api/clients/{client.pk}/")

        self.assertEqual(response.status_code, 405)
        self.assertTrue(Client.objects.filter(pk=client.pk).exists())
