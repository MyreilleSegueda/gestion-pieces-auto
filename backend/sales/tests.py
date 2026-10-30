from decimal import Decimal
from threading import Barrier, Thread
from unittest import skipUnless

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.db import close_old_connections, connection
from django.test import TestCase, TransactionTestCase
from rest_framework.test import APIClient

from inventory.models import Categorie, MouvementStock, PieceDetachee
from invoicing.models import Facture

from .models import LigneVente, Vente


class VenteApiTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="vendeur-test",
            password="MotDePasseTest-2026",
        )
        group = Group.objects.create(name="Vendeur")
        self.user.groups.add(group)
        category = Categorie.objects.create(nom="Filtres")
        self.piece = PieceDetachee.objects.create(
            reference="FLT-001",
            designation="Filtre à huile",
            categorie=category,
            prix_achat="500.00",
            prix_vente="900.00",
            quantite_stock=5,
        )
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def create_sale(self, quantity=2):
        return self.client.post(
            "/api/ventes/",
            {
                "lignes": [{"piece": self.piece.pk, "quantite": quantity}],
            },
            format="json",
        )

    def test_sales_api_requires_authentication(self):
        response = APIClient().get("/api/ventes/")

        self.assertIn(response.status_code, (401, 403))

    def test_sale_draft_snapshots_price_without_changing_stock(self):
        response = self.create_sale()

        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["statut"], "BROUILLON")
        self.assertEqual(response.data["lignes"][0]["prix_unitaire"], "900.00")
        self.piece.refresh_from_db()
        self.assertEqual(self.piece.quantite_stock, 5)

        self.piece.prix_vente = "1200.00"
        self.piece.save()
        self.assertEqual(LigneVente.objects.get().prix_unitaire, Decimal("900.00"))

    def test_sale_rejects_piece_with_legacy_negative_price(self):
        self.piece.prix_vente = Decimal("-1.00")
        self.piece.save()

        response = self.create_sale()

        self.assertEqual(response.status_code, 400)
        self.assertFalse(Vente.objects.exists())
        self.assertFalse(LigneVente.objects.exists())

    def test_sale_line_model_validation_rejects_negative_price(self):
        sale = Vente.objects.create(creee_par=self.user)
        line = LigneVente(
            vente=sale,
            piece=self.piece,
            reference_piece=self.piece.reference,
            designation=self.piece.designation,
            quantite=1,
            prix_unitaire=Decimal("-0.01"),
        )

        with self.assertRaises(ValidationError):
            line.full_clean()

    def test_validating_sale_decreases_stock_once(self):
        response = self.create_sale(quantity=3)
        sale_id = response.data["id"]

        validated = self.client.post(f"/api/ventes/{sale_id}/valider/")
        repeated = self.client.post(f"/api/ventes/{sale_id}/valider/")

        self.assertEqual(validated.status_code, 200, validated.data)
        self.assertEqual(validated.data["statut"], "VALIDEE")
        self.assertEqual(repeated.status_code, 400)
        self.piece.refresh_from_db()
        self.assertEqual(self.piece.quantite_stock, 2)
        self.assertEqual(MouvementStock.objects.filter(type_mouvement="SORTIE").count(), 1)
        self.assertEqual(Facture.objects.filter(vente_id=sale_id).count(), 1)

    def test_insufficient_stock_rolls_back_sale_validation(self):
        response = self.create_sale(quantity=6)
        sale_id = response.data["id"]

        validation = self.client.post(f"/api/ventes/{sale_id}/valider/")

        self.assertEqual(validation.status_code, 400)
        self.piece.refresh_from_db()
        self.assertEqual(self.piece.quantite_stock, 5)
        self.assertEqual(MouvementStock.objects.count(), 0)
        self.assertEqual(Vente.objects.get(pk=sale_id).statut, "BROUILLON")
        self.assertFalse(Facture.objects.filter(vente_id=sale_id).exists())

    def test_draft_can_be_cancelled_without_changing_stock(self):
        response = self.create_sale()

        cancelled = self.client.post(f"/api/ventes/{response.data['id']}/annuler/")

        self.assertEqual(cancelled.status_code, 200)
        self.assertEqual(cancelled.data["statut"], "ANNULEE")
        self.piece.refresh_from_db()
        self.assertEqual(self.piece.quantite_stock, 5)
        self.assertEqual(MouvementStock.objects.count(), 0)

    def test_draft_sale_can_be_edited_without_changing_stock_or_saved_price(self):
        response = self.create_sale()
        sale_id = response.data["id"]
        self.piece.prix_vente = Decimal("1200.00")
        self.piece.save()

        update = self.client.patch(
            f"/api/ventes/{sale_id}/",
            {"lignes": [{"piece": self.piece.pk, "quantite": 4}]},
            format="json",
        )

        self.assertEqual(update.status_code, 200, update.data)
        self.assertEqual(update.data["statut"], "BROUILLON")
        self.assertEqual(update.data["lignes"][0]["quantite"], 4)
        self.assertEqual(update.data["lignes"][0]["prix_unitaire"], "900.00")
        self.piece.refresh_from_db()
        self.assertEqual(self.piece.quantite_stock, 5)
        self.assertEqual(MouvementStock.objects.count(), 0)

    def test_validated_sale_cannot_be_edited(self):
        response = self.create_sale()
        sale_id = response.data["id"]
        validated = self.client.post(f"/api/ventes/{sale_id}/valider/")
        self.assertEqual(validated.status_code, 200)

        update = self.client.patch(
            f"/api/ventes/{sale_id}/",
            {"lignes": [{"piece": self.piece.pk, "quantite": 1}]},
            format="json",
        )

        self.assertEqual(update.status_code, 400)
        self.assertEqual(Vente.objects.get(pk=sale_id).statut, "VALIDEE")
        self.assertEqual(LigneVente.objects.get(vente_id=sale_id).quantite, 2)
        self.assertEqual(MouvementStock.objects.filter(type_mouvement="SORTIE").count(), 1)


@skipUnless(connection.vendor == "postgresql", "Ce test exige PostgreSQL.")
class VenteConcurrencyTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="vendeur-concurrent",
            password="MotDePasseTest-2026",
        )
        self.user.groups.add(Group.objects.create(name="Vendeur"))
        category = Categorie.objects.create(nom="Concurrent")
        self.piece = PieceDetachee.objects.create(
            reference="CON-001",
            designation="Pièce concurrente",
            categorie=category,
            prix_achat="10.00",
            prix_vente="20.00",
            quantite_stock=5,
        )
        self.sale = Vente.objects.create(creee_par=self.user)
        LigneVente.objects.create(
            vente=self.sale,
            piece=self.piece,
            reference_piece=self.piece.reference,
            designation=self.piece.designation,
            quantite=1,
            prix_unitaire=self.piece.prix_vente,
        )

    def test_validation_and_cancellation_are_serialized(self):
        barrier = Barrier(2)
        outcomes = {}
        errors = []

        def send_action(action):
            close_old_connections()
            try:
                client = APIClient()
                client.force_authenticate(get_user_model().objects.get(pk=self.user.pk))
                barrier.wait(timeout=10)
                response = client.post(f"/api/ventes/{self.sale.pk}/{action}/")
                outcomes[action] = response.status_code
            except BaseException as error:
                errors.append(error)
            finally:
                close_old_connections()

        workers = [
            Thread(target=send_action, args=("valider",)),
            Thread(target=send_action, args=("annuler",)),
        ]
        for worker in workers:
            worker.start()
        for worker in workers:
            worker.join(timeout=20)

        self.assertFalse(any(worker.is_alive() for worker in workers))
        self.assertEqual(errors, [])
        self.assertEqual(set(outcomes.values()), {200, 400})

        self.sale.refresh_from_db()
        self.piece.refresh_from_db()
        movement_count = MouvementStock.objects.filter(
            reference_document=self.sale.reference,
            type_mouvement="SORTIE",
        ).count()
        invoice_count = Facture.objects.filter(vente=self.sale).count()

        if self.sale.statut == "VALIDEE":
            self.assertEqual(self.piece.quantite_stock, 4)
            self.assertEqual(movement_count, 1)
            self.assertEqual(invoice_count, 1)
        else:
            self.assertEqual(self.sale.statut, "ANNULEE")
            self.assertEqual(self.piece.quantite_stock, 5)
            self.assertEqual(movement_count, 0)
            self.assertEqual(invoice_count, 0)
