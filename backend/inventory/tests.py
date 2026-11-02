import json

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.test import Client, TestCase
from rest_framework.test import APIClient

from .models import Categorie, MouvementStock, PieceDetachee


class InventoryApiTests(TestCase):
	def setUp(self):
		self.user = get_user_model().objects.create_user(
			username="stock-manager",
			password="MotDePasseTest-2026",
		)
		group, _ = Group.objects.get_or_create(name="Gestionnaire de stock")
		self.user.groups.add(group)
		self.category = Categorie.objects.create(nom="Freinage")
		self.piece = PieceDetachee.objects.create(
			reference="FRE-001",
			designation="Plaquette de frein",
			categorie=self.category,
			prix_achat="1000.00",
			prix_vente="1500.00",
			quantite_stock=5,
			seuil_minimal=2,
		)
		self.client = APIClient()
		self.client.force_authenticate(self.user)

	def test_inventory_api_requires_authentication(self):
		response = APIClient().get("/api/pieces/")

		self.assertIn(response.status_code, (401, 403))

	def test_staff_without_business_role_cannot_read_or_change_stock(self):
		staff_user = get_user_model().objects.create_user(
			username="staff-without-stock-role",
			password="MotDePasseTest-2026",
			is_staff=True,
		)
		client = APIClient()
		client.force_authenticate(staff_user)

		read_response = client.get("/api/pieces/")
		write_response = client.post(
			"/api/pieces/",
			{"reference": "DENIED", "designation": "Denied"},
			format="json",
		)

		self.assertEqual(read_response.status_code, 403)
		self.assertEqual(write_response.status_code, 403)

	def test_login_session_with_stock_role_can_record_movement(self):
		client = Client(enforce_csrf_checks=True)
		csrf = client.get("/api/auth/csrf/")
		login = client.post(
			"/api/auth/connexion/",
			data=json.dumps({
				"username": "stock-manager",
				"password": "MotDePasseTest-2026",
			}),
			content_type="application/json",
			HTTP_X_CSRFTOKEN=csrf.json()["csrfToken"],
		)
		self.assertEqual(login.status_code, 200)

		csrf = client.get("/api/auth/csrf/")
		response = client.post(
			"/api/mouvements/",
			data=json.dumps({
				"piece": self.piece.pk,
				"type_mouvement": "ENTREE",
				"quantite": 1,
				"motif": "Parcours session",
			}),
			content_type="application/json",
			HTTP_X_CSRFTOKEN=csrf.json()["csrfToken"],
			HTTP_IDEMPOTENCY_KEY="07b56a30-07f7-453d-88ef-77a60245b605",
		)

		self.assertEqual(response.status_code, 201)
		self.piece.refresh_from_db()
		self.assertEqual(self.piece.quantite_stock, 6)

	def test_piece_stock_cannot_be_changed_directly(self):
		response = self.client.patch(
			f"/api/pieces/{self.piece.pk}/",
			{"quantite_stock": 50},
			format="json",
		)

		self.assertEqual(response.status_code, 200)
		self.piece.refresh_from_db()
		self.assertEqual(self.piece.quantite_stock, 5)

	def test_piece_api_rejects_negative_prices(self):
		create_response = self.client.post(
			"/api/pieces/",
			{
				"reference": "FRE-NEG",
				"designation": "Pièce prix négatif",
				"categorie": self.category.pk,
				"prix_achat": "-1.00",
				"prix_vente": "1.00",
			},
			format="json",
		)
		purchase_update = self.client.patch(
			f"/api/pieces/{self.piece.pk}/",
			{"prix_achat": "-0.01"},
			format="json",
		)
		sale_update = self.client.patch(
			f"/api/pieces/{self.piece.pk}/",
			{"prix_vente": "-0.01"},
			format="json",
		)

		self.assertEqual(create_response.status_code, 400)
		self.assertEqual(purchase_update.status_code, 400)
		self.assertEqual(sale_update.status_code, 400)
		self.assertFalse(PieceDetachee.objects.filter(reference="FRE-NEG").exists())
		self.piece.refresh_from_db()
		self.assertEqual(str(self.piece.prix_achat), "1000.00")
		self.assertEqual(str(self.piece.prix_vente), "1500.00")

	def test_piece_model_validation_rejects_negative_prices(self):
		for field in ("prix_achat", "prix_vente"):
			with self.subTest(field=field):
				setattr(self.piece, field, -1)
				with self.assertRaises(ValidationError):
					self.piece.full_clean()
			setattr(
				self.piece,
				field,
				"1000.00" if field == "prix_achat" else "1500.00",
			)

	def test_piece_cannot_be_permanently_deleted_from_api(self):
		response = self.client.delete(f"/api/pieces/{self.piece.pk}/")

		self.assertEqual(response.status_code, 405)
		self.assertTrue(PieceDetachee.objects.filter(pk=self.piece.pk).exists())

	def test_referenced_category_deletion_returns_conflict(self):
		response = self.client.delete(f"/api/categories/{self.category.pk}/")

		self.assertEqual(response.status_code, 409)
		self.assertIn("pièces y sont encore rattachées", response.data["detail"])
		self.assertTrue(Categorie.objects.filter(pk=self.category.pk).exists())
		self.assertTrue(PieceDetachee.objects.filter(pk=self.piece.pk).exists())

	def test_unused_category_can_be_deleted(self):
		category = Categorie.objects.create(nom="Sans pièce")

		response = self.client.delete(f"/api/categories/{category.pk}/")

		self.assertEqual(response.status_code, 204)
		self.assertFalse(Categorie.objects.filter(pk=category.pk).exists())

	def test_stock_movement_updates_quantity(self):
		response = self.client.post(
			"/api/mouvements/",
			{
				"piece": self.piece.pk,
				"type_mouvement": "SORTIE",
				"quantite": 3,
				"motif": "Vente comptoir",
			},
			format="json",
			HTTP_IDEMPOTENCY_KEY="c9b9bd20-4d4b-4d90-923e-f979d5ff6322",
		)

		self.assertEqual(response.status_code, 201, response.data)
		self.assertEqual(response.data["utilisateur_nom"], "stock-manager")
		self.piece.refresh_from_db()
		self.assertEqual(self.piece.quantite_stock, 2)
		self.assertEqual(MouvementStock.objects.count(), 1)
		self.assertEqual(
			MouvementStock.objects.get().utilisateur,
			self.user,
		)

	def test_inventory_correction_can_set_stock_to_zero(self):
		response = self.client.post(
			"/api/mouvements/",
			{
				"piece": self.piece.pk,
				"type_mouvement": "CORRECTION",
				"quantite": 0,
				"motif": "Inventaire physique",
			},
			format="json",
			HTTP_IDEMPOTENCY_KEY="a81a0bb5-1c90-44b3-b7d7-9e97cf8d70aa",
		)

		self.assertEqual(response.status_code, 201, response.data)
		self.piece.refresh_from_db()
		self.assertEqual(self.piece.quantite_stock, 0)

	def test_stock_movement_cannot_make_quantity_negative(self):
		response = self.client.post(
			"/api/mouvements/",
			{
				"piece": self.piece.pk,
				"type_mouvement": "SORTIE",
				"quantite": 6,
				"motif": "Sortie supérieure au stock",
			},
			format="json",
			HTTP_IDEMPOTENCY_KEY="8e03f356-4c36-4bc3-9eb3-84ff97c829d2",
		)

		self.assertEqual(response.status_code, 400)
		self.piece.refresh_from_db()
		self.assertEqual(self.piece.quantite_stock, 5)
		self.assertEqual(MouvementStock.objects.count(), 0)

	def test_duplicate_movement_request_changes_stock_only_once(self):
		payload = {
			"piece": self.piece.pk,
			"type_mouvement": "ENTREE",
			"quantite": 2,
			"motif": "Réception fournisseur",
		}
		key = "454eab4d-6a6d-4c6a-9c52-6f1a82b4a429"

		first = self.client.post(
			"/api/mouvements/",
			payload,
			format="json",
			HTTP_IDEMPOTENCY_KEY=key,
		)
		second = self.client.post(
			"/api/mouvements/",
			payload,
			format="json",
			HTTP_IDEMPOTENCY_KEY=key,
		)

		self.assertEqual(first.status_code, 201)
		self.assertEqual(second.status_code, 200)
		self.assertEqual(first.data["id"], second.data["id"])
		self.assertEqual(
			first.data["idempotency_key"],
			"454eab4d-6a6d-4c6a-9c52-6f1a82b4a429",
		)
		self.piece.refresh_from_db()
		self.assertEqual(self.piece.quantite_stock, 7)
		self.assertEqual(MouvementStock.objects.count(), 1)

	def test_another_user_cannot_replay_movement_response(self):
		key = "886972b0-5803-47e1-a07b-5ba99b144b18"
		payload = {
			"piece": self.piece.pk,
			"type_mouvement": "ENTREE",
			"quantite": 2,
			"motif": "Réception fournisseur",
		}
		self.client.post(
			"/api/mouvements/",
			payload,
			format="json",
			HTTP_IDEMPOTENCY_KEY=key,
		)
		other_user = get_user_model().objects.create_user(
			username="another-stock-manager",
			password="MotDePasseTest-2026",
		)
		group = Group.objects.get(name="Gestionnaire de stock")
		other_user.groups.add(group)
		other_client = APIClient()
		other_client.force_authenticate(other_user)

		response = other_client.post(
			"/api/mouvements/",
			payload,
			format="json",
			HTTP_IDEMPOTENCY_KEY=key,
		)

		self.assertEqual(response.status_code, 409)
		self.assertNotIn("utilisateur_nom", response.data)

	def test_reused_idempotency_key_with_different_payload_is_rejected(self):
		key = "e06966d1-f53c-4bd0-8d49-72a3495daa68"
		payload = {
			"piece": self.piece.pk,
			"type_mouvement": "ENTREE",
			"quantite": 2,
			"motif": "Réception fournisseur",
		}
		self.client.post(
			"/api/mouvements/",
			payload,
			format="json",
			HTTP_IDEMPOTENCY_KEY=key,
		)

		response = self.client.post(
			"/api/mouvements/",
			{**payload, "quantite": 3},
			format="json",
			HTTP_IDEMPOTENCY_KEY=key,
		)

		self.assertEqual(response.status_code, 409)
		self.piece.refresh_from_db()
		self.assertEqual(self.piece.quantite_stock, 7)
		self.assertEqual(MouvementStock.objects.count(), 1)

	def test_movement_requires_idempotency_key(self):
		response = self.client.post(
			"/api/mouvements/",
			{
				"piece": self.piece.pk,
				"type_mouvement": "ENTREE",
				"quantite": 1,
				"motif": "Réception",
			},
			format="json",
		)

		self.assertEqual(response.status_code, 400)
		self.assertEqual(MouvementStock.objects.count(), 0)

	def test_stock_movement_cannot_be_deleted(self):
		movement = MouvementStock.objects.create(
			piece=self.piece,
			type_mouvement="ENTREE",
			quantite=1,
			motif="Réception",
		)

		response = self.client.delete(f"/api/mouvements/{movement.pk}/")

		self.assertEqual(response.status_code, 405)
		self.assertTrue(MouvementStock.objects.filter(pk=movement.pk).exists())

	def test_store_manager_can_read_but_not_write_inventory(self):
		manager = get_user_model().objects.create_user(
			username="responsable-magasin",
			password="MotDePasseTest-2026",
		)
		group = Group.objects.create(name="Responsable magasin")
		manager.groups.add(group)
		manager_client = APIClient()
		manager_client.force_authenticate(manager)

		read_response = manager_client.get("/api/pieces/")
		write_response = manager_client.post(
			"/api/categories/",
			{"nom": "Moteur"},
			format="json",
		)

		self.assertEqual(read_response.status_code, 200)
		self.assertEqual(write_response.status_code, 403)
