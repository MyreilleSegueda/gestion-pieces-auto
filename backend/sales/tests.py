from decimal import Decimal
from threading import Barrier, Thread
from unittest import skipUnless

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.db import close_old_connections, connection
from django.db.models import Sum
from django.test import TestCase, TransactionTestCase
from rest_framework.test import APIClient

from inventory.models import Categorie, MouvementStock, PieceDetachee
from invoicing.models import Facture
from caisse.models import Encaissement, Remboursement

from .models import LigneRetourVente, LigneVente, RetourVente, Vente


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

    def test_staff_without_sales_role_cannot_read_or_create_sales(self):
        staff_user = get_user_model().objects.create_user(
            username="staff-without-sales-role",
            password="MotDePasseTest-2026",
            is_staff=True,
        )
        client = APIClient()
        client.force_authenticate(staff_user)

        self.assertEqual(client.get("/api/ventes/").status_code, 403)
        self.assertEqual(
            client.post(
                "/api/ventes/",
                {"lignes": [{"piece": self.piece.pk, "quantite": 1}]},
                format="json",
            ).status_code,
            403,
        )

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

    def create_administrator(self):
        admin = get_user_model().objects.create_user(
            username="return-admin",
            password="test-password",
        )
        admin.groups.add(Group.objects.create(name="Administrateur"))
        return admin

    def validated_sale(self, quantity=2):
        created = self.create_sale(quantity)
        self.assertEqual(created.status_code, 201)
        response = self.client.post(f"/api/ventes/{created.data['id']}/valider/")
        self.assertEqual(response.status_code, 200)
        return created.data["id"], created.data["lignes"][0]

    def test_partial_return_requires_admin_authorization_and_restock_is_once(self):
        sale_id, line = self.validated_sale(quantity=2)
        self.piece.refresh_from_db()
        initial_stock = self.piece.quantite_stock
        key = "c789ec26-4d33-4aeb-9874-df412d697f47"
        requested = self.client.post(
            "/api/retours-ventes/",
            {
                "vente": sale_id,
                "type_operation": RetourVente.RETOUR,
                "motif": "Pièce non adaptée",
                "lignes": [{"ligne_vente": line["id"], "quantite": 1}],
            },
            format="json",
            HTTP_IDEMPOTENCY_KEY=key,
        )
        self.assertEqual(requested.status_code, 201, requested.data)
        self.assertEqual(requested.data["montant_total"], "900.00")
        self.piece.refresh_from_db()
        self.assertEqual(self.piece.quantite_stock, initial_stock)

        forbidden = self.client.post(
            f"/api/retours-ventes/{requested.data['id']}/autoriser/",
            {"remise_en_stock": True},
            format="json",
        )
        self.assertEqual(forbidden.status_code, 403)

        self.client.force_authenticate(self.create_administrator())
        approved = self.client.post(
            f"/api/retours-ventes/{requested.data['id']}/autoriser/",
            {"remise_en_stock": True},
            format="json",
        )
        repeated = self.client.post(
            f"/api/retours-ventes/{requested.data['id']}/autoriser/",
            {"remise_en_stock": True},
            format="json",
        )
        self.assertEqual(approved.status_code, 200, approved.data)
        self.assertEqual(repeated.status_code, 200)
        self.piece.refresh_from_db()
        self.assertEqual(self.piece.quantite_stock, initial_stock + 1)
        self.assertEqual(
            MouvementStock.objects.filter(
                type_mouvement="RETOUR",
                reference_document=requested.data["reference"],
            ).count(),
            1,
        )
        self.assertEqual(
            LigneRetourVente.objects.filter(retour_id=requested.data["id"]).aggregate(
                total=Sum("quantite")
            )["total"],
            1,
        )

        duplicate_return = self.client.post(
            "/api/retours-ventes/",
            {
                "vente": sale_id,
                "type_operation": RetourVente.RETOUR,
                "motif": "Trop de pièces",
                "lignes": [{"ligne_vente": line["id"], "quantite": 2}],
            },
            format="json",
            HTTP_IDEMPOTENCY_KEY="c12c6fb9-5e53-4f98-b186-22676a9e33af",
        )
        self.assertEqual(duplicate_return.status_code, 400)

        invoice = self.client.get("/api/factures/").data[0]
        self.assertEqual(invoice["montant_avoirs"], "900.00")
        self.assertEqual(invoice["solde_restant"], "900.00")
        invoice_model = Facture.objects.get(vente_id=sale_id)
        Encaissement.objects.create(
            facture=invoice_model,
            montant=Decimal("900.00"),
            mode_paiement="ESPECES",
            encaisse_par=self.user,
        )
        settled_invoice = self.client.get("/api/factures/").data[0]
        self.assertEqual(settled_invoice["etat_paiement"], "Payée")
        self.assertEqual(settled_invoice["solde_restant"], "0.00")

    def test_sale_cancellation_is_admin_approved_traceable_and_financially_separate(self):
        sale_id, _line = self.validated_sale(quantity=2)
        invoice = Facture.objects.get(vente_id=sale_id)
        payment = Encaissement.objects.create(
            facture=invoice,
            montant=Decimal("1000.00"),
            mode_paiement="ESPECES",
            encaisse_par=self.user,
        )
        self.piece.refresh_from_db()
        before = self.piece.quantite_stock

        requested = self.client.post(
            f"/api/ventes/{sale_id}/demander-annulation/",
            {"motif": "Commande annulée par le client"},
            format="json",
            HTTP_IDEMPOTENCY_KEY="e301fa6d-5eed-4623-a16e-3c3cf8fddc1f",
        )
        self.assertEqual(requested.status_code, 201, requested.data)
        self.assertEqual(requested.data["type_operation"], RetourVente.ANNULATION)
        self.assertEqual(requested.data["montant_total"], "1800.00")
        self.assertEqual(Vente.objects.get(pk=sale_id).statut, "VALIDEE")

        admin = self.create_administrator()
        self.client.force_authenticate(admin)
        approved = self.client.post(
            f"/api/retours-ventes/{requested.data['id']}/autoriser/",
            {"remise_en_stock": True},
            format="json",
        )
        repeated = self.client.post(
            f"/api/retours-ventes/{requested.data['id']}/autoriser/",
            {"remise_en_stock": True},
            format="json",
        )
        self.assertEqual(approved.status_code, 200, approved.data)
        self.assertEqual(repeated.status_code, 200)
        self.assertEqual(Vente.objects.get(pk=sale_id).statut, "ANNULEE")
        self.piece.refresh_from_db()
        self.assertEqual(self.piece.quantite_stock, before + 2)
        self.assertTrue(Facture.objects.filter(pk=invoice.pk).exists())
        self.assertEqual(Remboursement.objects.filter(
            encaissement=payment,
            retour_vente_id=requested.data["id"],
            statut=Remboursement.EN_ATTENTE,
        ).count(), 1)

        invoice_data = self.client.get("/api/factures/").data[0]
        self.assertEqual(invoice_data["etat_paiement"], "Annulée")
        self.assertEqual(invoice_data["solde_restant"], "0.00")
        self.assertEqual(Encaissement.objects.filter(pk=payment.pk).count(), 1)

    def test_return_without_restock_is_credited_but_does_not_change_stock(self):
        sale_id, line = self.validated_sale(quantity=2)
        self.piece.refresh_from_db()
        before = self.piece.quantite_stock
        requested = self.client.post(
            "/api/retours-ventes/",
            {
                "vente": sale_id,
                "type_operation": RetourVente.RETOUR,
                "motif": "Pièce endommagée",
                "lignes": [{"ligne_vente": line["id"], "quantite": 1}],
            },
            format="json",
            HTTP_IDEMPOTENCY_KEY="8b3cf342-191f-47d7-af14-e4e0ea4af28b",
        )
        self.client.force_authenticate(self.create_administrator())
        approved = self.client.post(
            f"/api/retours-ventes/{requested.data['id']}/autoriser/",
            {"remise_en_stock": False},
            format="json",
        )
        self.assertEqual(approved.status_code, 200)
        self.piece.refresh_from_db()
        self.assertEqual(self.piece.quantite_stock, before)
        invoice = self.client.get("/api/factures/").data[0]
        self.assertEqual(invoice["montant_avoirs"], "900.00")
        self.assertFalse(MouvementStock.objects.filter(
            type_mouvement="RETOUR",
            reference_document=requested.data["reference"],
        ).exists())


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
