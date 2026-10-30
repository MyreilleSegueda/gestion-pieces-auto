import json

from django.contrib.auth import get_user_model
from django.test import Client, TestCase


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
