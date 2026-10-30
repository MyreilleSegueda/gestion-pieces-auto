import json
from threading import Barrier, Thread
from unittest import skipUnless

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db import close_old_connections, connection
from django.test import Client, TestCase, TransactionTestCase
from rest_framework.test import APIClient

@skipUnless(connection.vendor == "postgresql", "Ce test exige PostgreSQL.")
class AdministratorConcurrencyTests(TransactionTestCase):
        reset_sequences = True

        def setUp(self):
                self.admin_group = Group.objects.create(name="Administrateur")
                self.users = [
                        get_user_model().objects.create_user(
                                username=f"group-admin-{index}",
                                password="MotDePasseTest-2026",
                        )
                        for index in range(2)
                ]
                for user in self.users:
                        user.groups.add(self.admin_group)

        def test_concurrent_role_removal_keeps_one_active_administrator(self):
                barrier = Barrier(2)
                statuses = []
                errors = []

                def remove_role(user_id):
                        close_old_connections()
                        try:
                                user = get_user_model().objects.get(pk=user_id)
                                client = APIClient()
                                client.force_authenticate(user)
                                barrier.wait(timeout=10)
                                response = client.patch(
                                        f"/api/utilisateurs/{user_id}/",
                                        {"roles": []},
                                        format="json",
                                )
                                statuses.append(response.status_code)
                        except BaseException as error:
                                errors.append(error)
                        finally:
                                close_old_connections()

                workers = [
                        Thread(target=remove_role, args=(user.pk,))
                        for user in self.users
                ]
                for worker in workers:
                        worker.start()
                for worker in workers:
                        worker.join(timeout=20)

                self.assertFalse(any(worker.is_alive() for worker in workers))
                self.assertEqual(errors, [])
                self.assertCountEqual(statuses, [200, 400])
                active_admins = get_user_model().objects.filter(
                        is_active=True,
                        groups__name="Administrateur",
                ).distinct().count()
                self.assertEqual(active_admins, 1)
from rest_framework.test import APIClient


class UserApiTests(TestCase):
        def setUp(self):
                user_model = get_user_model()
                self.admin = user_model.objects.create_user(
                        username="admin-api",
                        password="MotDePasseTest-2026",
                        is_staff=True,
                )
                self.regular_user = user_model.objects.create_user(
                        username="vendeur-api",
                        password="MotDePasseTest-2026",
                )
                self.client = APIClient()

        def test_user_api_is_admin_only(self):
                self.client.force_authenticate(self.regular_user)

                response = self.client.get("/api/utilisateurs/")

                self.assertEqual(response.status_code, 403)

        def test_login_session_can_access_admin_user_api(self):
                client = Client(enforce_csrf_checks=True)
                csrf = client.get("/api/auth/csrf/")
                login = client.post(
                        "/api/auth/connexion/",
                        data=json.dumps({
                                "username": "admin-api",
                                "password": "MotDePasseTest-2026",
                        }),
                        content_type="application/json",
                        HTTP_X_CSRFTOKEN=csrf.json()["csrfToken"],
                )

                self.assertEqual(login.status_code, 200)
                self.assertEqual(client.get("/api/auth/session/").status_code, 200)
                self.assertEqual(client.get("/api/utilisateurs/").status_code, 200)

        def test_admin_can_create_user_with_valid_password_and_role(self):
                group, _ = Group.objects.get_or_create(name="Vendeur")
                self.client.force_authenticate(self.admin)

                response = self.client.post(
                        "/api/utilisateurs/",
                        {
                                "username": "nouveau-vendeur",
                                "mot_de_passe": "BonMotDePasse-2026!",
                                "roles": [group.name],
                        },
                        format="json",
                )

                self.assertEqual(response.status_code, 201, response.data)
                created_user = get_user_model().objects.get(username="nouveau-vendeur")
                self.assertTrue(created_user.check_password("BonMotDePasse-2026!"))
                self.assertEqual(list(created_user.groups.values_list("name", flat=True)), ["Vendeur"])

        def test_admin_cannot_create_user_with_weak_password(self):
                self.client.force_authenticate(self.admin)

                response = self.client.post(
                        "/api/utilisateurs/",
                        {
                                "username": "nouveau-vendeur",
                                "mot_de_passe": "123",
                        },
                        format="json",
                )

                self.assertEqual(response.status_code, 400)
                self.assertFalse(
                        get_user_model().objects.filter(username="nouveau-vendeur").exists()
                )

        def test_admin_can_list_existing_roles(self):
                Group.objects.create(name="Gestionnaire de stock")
                self.client.force_authenticate(self.admin)

                response = self.client.get("/api/roles/")

                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.data[0]["name"], "Gestionnaire de stock")

        def test_admin_can_inspect_effective_api_and_django_permissions(self):
                Group.objects.get_or_create(name="Administrateur")
                Group.objects.get_or_create(name="Caissier")
                Group.objects.get_or_create(name="Gestionnaire de stock")
                Group.objects.get_or_create(name="Responsable magasin")
                Group.objects.get_or_create(name="Vendeur")
                self.client.force_authenticate(self.admin)

                response = self.client.get("/api/roles/effectifs/")
                       
                self.assertEqual(response.status_code, 200)
                roles = {role["name"]: role for role in response.data}
                self.assertEqual(roles["Caissier"]["permissions_api"]["caisse"], "gestion")
                self.assertEqual(roles["Administrateur"]["permissions_api"]["caisse"], "gestion")
                self.assertEqual(roles["Vendeur"]["permissions_api"]["caisse"], "absent")
                self.assertEqual(roles["Gestionnaire de stock"]["permissions_api"]["stock"], "gestion")
                self.assertIn("permissions_django", roles["Vendeur"])

        def test_non_admin_cannot_inspect_role_permissions(self):
                self.client.force_authenticate(self.regular_user)

                response = self.client.get("/api/roles/effectifs/")

                self.assertEqual(response.status_code, 403)

        def test_administrator_group_can_access_user_api(self):
                group = Group.objects.create(name="Administrateur")
                self.regular_user.groups.add(group)
                self.client.force_authenticate(self.regular_user)

                response = self.client.get("/api/utilisateurs/")

                self.assertEqual(response.status_code, 200)

        def test_admin_cannot_deactivate_own_account(self):
                self.client.force_authenticate(self.admin)

                response = self.client.patch(
                        f"/api/utilisateurs/{self.admin.pk}/",
                        {"is_active": False},
                        format="json",
                )

                self.assertEqual(response.status_code, 400)
                self.admin.refresh_from_db()
                self.assertTrue(self.admin.is_active)

        def test_last_group_administrator_cannot_remove_own_role(self):
                self.admin.is_active = False
                self.admin.save(update_fields=["is_active"])
                admin_group = Group.objects.create(name="Administrateur")
                self.regular_user.groups.add(admin_group)
                self.client.force_authenticate(self.regular_user)

                response = self.client.patch(
                        f"/api/utilisateurs/{self.regular_user.pk}/",
                        {"roles": []},
                        format="json",
                )

                self.assertEqual(response.status_code, 400)
                self.assertTrue(
                        self.regular_user.groups.filter(name="Administrateur").exists()
                )

        def test_user_api_does_not_allow_permanent_deletion(self):
                self.client.force_authenticate(self.admin)

                response = self.client.delete(f"/api/utilisateurs/{self.regular_user.pk}/")

                self.assertEqual(response.status_code, 405)
                self.assertTrue(
                        get_user_model().objects.filter(pk=self.regular_user.pk).exists()
                )
