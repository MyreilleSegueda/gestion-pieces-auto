import json

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import Client, TestCase

from .role_permissions import ROLE_MODULE_ACCESS, has_module_access


class AuthenticationApiTests(TestCase):
	def setUp(self):
		self.user = get_user_model().objects.create_user(
			username="gestionnaire",
			password="MotDePasseTest-2026",
			first_name="Marie",
			last_name="Kaboré",
		)

	def test_session_requires_authentication(self):
		response = self.client.get("/api/auth/session/")

		self.assertEqual(response.status_code, 401)

	def test_login_session_and_logout(self):
		client = Client(enforce_csrf_checks=True)
		csrf_response = client.get("/api/auth/csrf/")
		self.assertIn("csrftoken", csrf_response.cookies)

		response = client.post(
			"/api/auth/connexion/",
			data=json.dumps({
				"username": "gestionnaire",
				"password": "MotDePasseTest-2026",
			}),
			content_type="application/json",
			HTTP_X_CSRFTOKEN=csrf_response.json()["csrfToken"],
		)

		self.assertEqual(response.status_code, 200)
		self.assertEqual(response.json()["username"], "gestionnaire")
		self.assertEqual(
			client.get("/api/auth/session/").json()["first_name"],
			"Marie",
		)

		csrf_response = client.get("/api/auth/csrf/")
		logout_response = client.post(
			"/api/auth/deconnexion/",
			HTTP_X_CSRFTOKEN=csrf_response.json()["csrfToken"],
		)

		self.assertEqual(logout_response.status_code, 200)
		self.assertEqual(client.get("/api/auth/session/").status_code, 401)

	def test_login_rejects_invalid_credentials(self):
		response = self.client.post(
			"/api/auth/connexion/",
			data=json.dumps({
				"username": "gestionnaire",
				"password": "incorrect",
			}),
			content_type="application/json",
		)

		self.assertEqual(response.status_code, 401)

	def test_login_rejects_non_object_json(self):
		response = self.client.post(
			"/api/auth/connexion/",
			data=json.dumps(["gestionnaire", "password"]),
			content_type="application/json",
		)

		self.assertEqual(response.status_code, 400)

	def test_user_can_change_own_password_after_verifying_current_password(self):
		client = Client(enforce_csrf_checks=True)
		csrf = client.get("/api/auth/csrf/")
		login = client.post(
			"/api/auth/connexion/",
			data=json.dumps({
				"username": "gestionnaire",
				"password": "MotDePasseTest-2026",
			}),
			content_type="application/json",
			HTTP_X_CSRFTOKEN=csrf.json()["csrfToken"],
		)
		self.assertEqual(login.status_code, 200)

		csrf = client.get("/api/auth/csrf/")
		response = client.post(
			"/api/auth/mot-de-passe/",
			data=json.dumps({
				"current_password": "MotDePasseTest-2026",
				"new_password": "NouveauMotDePasse-2026!",
			}),
			content_type="application/json",
			HTTP_X_CSRFTOKEN=csrf.json()["csrfToken"],
		)

		self.assertEqual(response.status_code, 200)
		self.assertEqual(client.get("/api/auth/session/").status_code, 200)
		self.user.refresh_from_db()
		self.assertTrue(self.user.check_password("NouveauMotDePasse-2026!"))

	def test_password_change_rejects_wrong_current_and_weak_new_password(self):
		self.client.force_login(self.user)
		wrong_current = self.client.post(
			"/api/auth/mot-de-passe/",
			{
				"current_password": "incorrect",
				"new_password": "NouveauMotDePasse-2026!",
			},
			content_type="application/json",
		)
		weak_new = self.client.post(
			"/api/auth/mot-de-passe/",
			{
				"current_password": "MotDePasseTest-2026",
				"new_password": "123",
			},
			content_type="application/json",
		)

		self.assertEqual(wrong_current.status_code, 400)
		self.assertEqual(weak_new.status_code, 400)
		self.user.refresh_from_db()
		self.assertTrue(self.user.check_password("MotDePasseTest-2026"))

	def test_password_change_requires_authentication(self):
		response = self.client.post(
			"/api/auth/mot-de-passe/",
			{
				"current_password": "MotDePasseTest-2026",
				"new_password": "NouveauMotDePasse-2026!",
			},
			content_type="application/json",
		)

		self.assertIn(response.status_code, (401, 403))


class BusinessRoleMatrixTests(TestCase):
	def test_each_business_role_matches_the_declared_read_and_write_matrix(self):
		user_model = get_user_model()
		for role_name, modules in ROLE_MODULE_ACCESS.items():
			with self.subTest(role=role_name):
				user = user_model.objects.create_user(
					username=f"matrix-{role_name.lower().replace(' ', '-')}",
					password="MotDePasseTest-2026",
					is_staff=True,
				)
				user.groups.add(Group.objects.create(name=role_name))
				for module, access in modules.items():
					with self.subTest(module=module):
						self.assertEqual(
							has_module_access(user, module),
							access in {"lecture", "gestion"},
						)
						self.assertEqual(
							has_module_access(user, module, write=True),
							access == "gestion",
						)

	def test_staff_without_business_role_has_no_module_access(self):
		user = get_user_model().objects.create_user(
			username="staff-only-matrix",
			password="MotDePasseTest-2026",
			is_staff=True,
		)

		for module in {module for access in ROLE_MODULE_ACCESS.values() for module in access}:
			with self.subTest(module=module):
				self.assertFalse(has_module_access(user, module))
				self.assertFalse(has_module_access(user, module, write=True))

	def test_unknown_role_has_no_default_business_access(self):
		user = get_user_model().objects.create_user(
			username="unknown-role",
			password="MotDePasseTest-2026",
		)
		user.groups.add(Group.objects.create(name="Role externe"))

		for module in {module for access in ROLE_MODULE_ACCESS.values() for module in access}:
			with self.subTest(module=module):
				self.assertFalse(has_module_access(user, module))
				self.assertFalse(has_module_access(user, module, write=True))

	def test_superuser_retains_explicit_administrative_access(self):
		user = get_user_model().objects.create_superuser(
			username="global-administrator",
			email="admin@example.test",
			password="MotDePasseTest-2026",
		)

		for module in {module for access in ROLE_MODULE_ACCESS.values() for module in access}:
			with self.subTest(module=module):
				self.assertTrue(has_module_access(user, module))
				self.assertTrue(has_module_access(user, module, write=True))
