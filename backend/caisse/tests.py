
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from rest_framework.test import APIClient
from uuid import uuid4

from inventory.models import Categorie, PieceDetachee
from invoicing.models import Facture
from caisse.models import ClotureCaisse, Encaissement, Remboursement


class CaisseApiTests(TestCase):
    def setUp(self):
        user = get_user_model().objects.create_user(
            username="caissier-test",
            password="MotDePasseTest-2026",
        )

        vendeur_group, _ = Group.objects.get_or_create(name="Vendeur")
        caissier_group, _ = Group.objects.get_or_create(name="Caissier")
        user.groups.add(vendeur_group, caissier_group)

        category = Categorie.objects.create(nom="Transmission")

        self.piece = PieceDetachee.objects.create(
            reference="TRN-CAISSE-001",
            designation="Courroie de test",
            categorie=category,
            prix_achat="30000.00",
            prix_vente="50000.00",
            quantite_stock=10,
        )

        self.api_client = APIClient()
        self.api_client.force_authenticate(user)

    def create_validated_invoice(self):
        response = self.api_client.post(
            "/api/ventes/",
            {"lignes": [{"piece": self.piece.pk, "quantite": 2}]},
            format="json",
        )

        self.assertEqual(response.status_code, 201)

        sale_id = response.data["id"]

        validation_response = self.api_client.post(
            f"/api/ventes/{sale_id}/valider/"
        )

        self.assertEqual(validation_response.status_code, 200)

        return Facture.objects.get(vente_id=sale_id)

    def test_facture_impayee(self):
        facture = self.create_validated_invoice()

        response = self.api_client.get("/api/factures-a-encaisser/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["total_facture"], "100000.00")
        self.assertEqual(response.data[0]["total_encaisse"], "0.00")
        self.assertEqual(response.data[0]["solde_restant"], "100000.00")
        self.assertEqual(response.data[0]["etat_paiement"], "Impayée")

    def test_paiement_partiel_puis_complet(self):
        facture = self.create_validated_invoice()

        premier_paiement = self.api_client.post(
            "/api/encaissements/",
            {
                "facture_id": facture.pk,
                "montant": "40000.00",
                "mode_paiement": "ESPECES",
            },
            format="json",
            HTTP_IDEMPOTENCY_KEY=str(uuid4()),
        )

        self.assertEqual(premier_paiement.status_code, 201)

        response = self.api_client.get("/api/factures-a-encaisser/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data[0]["total_encaisse"], "40000.00")
        self.assertEqual(response.data[0]["solde_restant"], "60000.00")
        self.assertEqual(
            response.data[0]["etat_paiement"],
            "Partiellement payée",
        )

        deuxieme_paiement = self.api_client.post(
            "/api/encaissements/",
            {
                "facture_id": facture.pk,
                "montant": "60000.00",
                "mode_paiement": "MOBILE_MONEY",
            },
            format="json",
            HTTP_IDEMPOTENCY_KEY=str(uuid4()),
        )

        self.assertEqual(deuxieme_paiement.status_code, 201)

        response = self.api_client.get("/api/factures-a-encaisser/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data[0]["total_encaisse"], "100000.00")
        self.assertEqual(response.data[0]["solde_restant"], "0.00")
        self.assertEqual(response.data[0]["etat_paiement"], "Payée")

    def test_vendeur_seul_ne_peut_pas_acceder_a_la_caisse(self):
        user = get_user_model().objects.create_user(
            username="vendeur-seul",
            password="MotDePasseTest-2026",
        )
        vendeur_group, _ = Group.objects.get_or_create(name="Vendeur")
        user.groups.add(vendeur_group)

        client = APIClient()
        client.force_authenticate(user)

        response = client.get("/api/factures-a-encaisser/")

        self.assertEqual(response.status_code, 403)

    def test_utilisateur_staff_sans_role_ne_peut_pas_acceder_a_la_caisse(self):
        user = get_user_model().objects.create_user(
            username="staff-sans-role",
            password="MotDePasseTest-2026",
            is_staff=True,
        )

        client = APIClient()
        client.force_authenticate(user)

        response = client.get("/api/factures-a-encaisser/")

        self.assertEqual(response.status_code, 403)    

    def create_payment(self, facture, amount="2000.00", mode="ESPECES", key=None):
        key = key or str(uuid4())
        return self.api_client.post(
            "/api/encaissements/",
            {
                "facture_id": facture.pk,
                "montant": amount,
                "mode_paiement": mode,
            },
            format="json",
            HTTP_IDEMPOTENCY_KEY=key,
        )

    def create_refund(self, payment, amount, reason, key=None):
        return self.api_client.post(
            "/api/remboursements/",
            {
                "encaissement_id": payment.data["id"],
                "montant": amount,
                "motif": reason,
            },
            format="json",
            HTTP_IDEMPOTENCY_KEY=key or str(uuid4()),
        )

    def execute_refund(self, refund_id, reference="TEST-EXECUTION-001"):
        return self.api_client.post(
            f"/api/remboursements/{refund_id}/executer/",
            {"reference_execution": reference},
            format="json",
        )

    def create_administrator(self):
        user = get_user_model().objects.create_user(
            username="admin-caisse",
            password="test-password",
        )
        admin_group, _ = Group.objects.get_or_create(name="Administrateur")
        user.groups.add(admin_group)
        return user

    def test_paiement_idempotent_et_recu_reimprimable(self):
        facture = self.create_validated_invoice()
        key = str(uuid4())

        first = self.create_payment(facture, key=key)
        second = self.create_payment(facture, key=key)

        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(Encaissement.objects.filter(facture=facture).count(), 1)

        receipt_url = f"/api/encaissements/{first.data['id']}/recu/"
        receipt = self.api_client.get(receipt_url)
        reprinted = self.api_client.get(receipt_url)

        self.assertEqual(receipt.status_code, 200)
        self.assertEqual(receipt.data["encaissement"]["reference"], first.data["reference"])
        self.assertEqual(receipt.data["solde_restant_apres"], "98000.00")
        self.assertEqual(reprinted.status_code, 200)
        self.assertEqual(Encaissement.objects.filter(facture=facture).count(), 1)

    def test_paiement_exige_une_cle_et_refuse_sa_reutilisation_avec_un_autre_montant(self):
        facture = self.create_validated_invoice()
        missing_key = self.api_client.post(
            "/api/encaissements/",
            {
                "facture_id": facture.pk,
                "montant": "2000.00",
                "mode_paiement": "ESPECES",
            },
            format="json",
        )
        self.assertEqual(missing_key.status_code, 400)

        key = str(uuid4())
        first = self.create_payment(facture, amount="2000.00", key=key)
        changed_payload = self.create_payment(
            facture,
            amount="2500.00",
            key=key,
        )
        self.assertEqual(first.status_code, 201)
        self.assertEqual(changed_payload.status_code, 409)
        self.assertEqual(Encaissement.objects.filter(facture=facture).count(), 1)

    def test_facture_preserves_payment_history_and_current_balance(self):
        facture = self.create_validated_invoice()
        payment = self.create_payment(facture, amount="2500.00")
        self.assertEqual(payment.status_code, 201)

        response = self.api_client.get("/api/factures/")

        self.assertEqual(response.status_code, 200)
        invoice = response.data[0]
        self.assertEqual(invoice["montant_encaisse_brut"], "2500.00")
        self.assertEqual(invoice["total_encaisse"], "2500.00")
        self.assertEqual(invoice["solde_restant"], "97500.00")
        self.assertEqual(invoice["etat_paiement"], "Partiellement payée")
        self.assertEqual(
            invoice["historique_encaissements"][0]["reference"],
            payment.data["reference"],
        )

    def test_remboursement_en_attente_exige_un_administrateur(self):
        facture = self.create_validated_invoice()
        payment = self.create_payment(facture)
        self.assertEqual(payment.status_code, 201)

        refund_key = str(uuid4())
        requested = self.create_refund(
            payment,
            amount="1500.00",
            reason="Erreur de montant",
            key=refund_key,
        )
        retried = self.create_refund(
            payment,
            amount="1500.00",
            reason="Erreur de montant",
            key=refund_key,
        )
        self.assertEqual(requested.status_code, 201)
        self.assertEqual(retried.status_code, 200)
        self.assertEqual(Remboursement.objects.filter(encaissement_id=payment.data["id"]).count(), 1)
        self.assertEqual(requested.data["statut"], Remboursement.EN_ATTENTE)
        self.assertEqual(self.api_client.get("/api/remboursements/").status_code, 200)

        forbidden = self.api_client.post(
            f"/api/remboursements/{requested.data['id']}/approuver/"
        )
        self.assertEqual(forbidden.status_code, 403)

        self.api_client.force_authenticate(self.create_administrator())
        approved = self.api_client.post(
            f"/api/remboursements/{requested.data['id']}/approuver/"
        )
        self.assertEqual(approved.status_code, 200)
        self.assertEqual(approved.data["statut"], Remboursement.AUTORISE)
        invoice_data = self.api_client.get("/api/factures-a-encaisser/").data[0]
        self.assertEqual(invoice_data["total_encaisse"], "2000.00")
        self.assertEqual(invoice_data["solde_restant"], "98000.00")

        executed = self.execute_refund(
            requested.data["id"],
            reference="BANK-TRANSFER-REF-001",
        )
        self.assertEqual(executed.status_code, 200)
        self.assertEqual(executed.data["statut"], Remboursement.EXECUTE)
        self.assertEqual(executed.data["reference_execution"], "BANK-TRANSFER-REF-001")
        approved_again = self.api_client.post(
            f"/api/remboursements/{requested.data['id']}/approuver/"
        )
        self.assertEqual(approved_again.status_code, 200)
        self.assertEqual(Remboursement.objects.filter(
            encaissement_id=payment.data["id"],
            statut=Remboursement.EXECUTE,
        ).count(), 1)

        invoice_data = self.api_client.get("/api/factures-a-encaisser/").data[0]
        self.assertEqual(invoice_data["total_encaisse"], "500.00")
        self.assertEqual(invoice_data["solde_restant"], "99500.00")

    def test_refund_execution_requires_authorization_and_external_reference(self):
        facture = self.create_validated_invoice()
        payment = self.create_payment(facture)
        refund = self.create_refund(payment, "1000.00", "Refund check")

        unauthorised = self.execute_refund(refund.data["id"])
        self.assertEqual(unauthorised.status_code, 409)

        self.api_client.force_authenticate(self.create_administrator())
        approved = self.api_client.post(
            f"/api/remboursements/{refund.data['id']}/approuver/"
        )
        self.assertEqual(approved.data["statut"], Remboursement.AUTORISE)

        missing_reference = self.api_client.post(
            f"/api/remboursements/{refund.data['id']}/executer/",
            {},
            format="json",
        )
        self.assertEqual(missing_reference.status_code, 400)

        executed = self.execute_refund(refund.data["id"], "CASH-RECEIPT-91")
        repeated = self.execute_refund(refund.data["id"], "CASH-RECEIPT-91")
        self.assertEqual(executed.status_code, 200)
        self.assertEqual(repeated.status_code, 200)
        self.assertEqual(
            Remboursement.objects.filter(
                pk=refund.data["id"],
                statut=Remboursement.EXECUTE,
            ).count(),
            1,
        )

    def test_remboursement_depassement_refuse_et_rejet_libere_le_reservable(self):
        facture = self.create_validated_invoice()
        payment = self.create_payment(facture)

        over_refund = self.create_refund(
            payment,
            amount="2000.01",
            reason="Montant supérieur au paiement",
        )
        self.assertEqual(over_refund.status_code, 400)

        requested = self.create_refund(
            payment,
            amount="2000.00",
            reason="Paiement erroné",
        )
        self.api_client.force_authenticate(self.create_administrator())
        rejected = self.api_client.post(
            f"/api/remboursements/{requested.data['id']}/refuser/"
        )
        self.assertEqual(rejected.status_code, 200)
        self.assertEqual(rejected.data["statut"], Remboursement.REFUSE)

        next_request = self.create_refund(
            payment,
            amount="2000.00",
            reason="Nouvelle demande",
        )
        self.assertEqual(next_request.status_code, 201)

    def test_cloture_journaliere_detaillee_et_immutable(self):
        invoice = self.create_validated_invoice()
        payment = self.create_payment(invoice, amount="2500.00")
        self.assertEqual(payment.status_code, 201)
        refund = self.create_refund(
            payment,
            amount="500.00",
            reason="Retour partiel",
        )
        self.api_client.force_authenticate(self.create_administrator())
        approved = self.api_client.post(
            f"/api/remboursements/{refund.data['id']}/approuver/"
        )
        self.assertEqual(approved.status_code, 200)
        preview = self.api_client.get("/api/clotures-caisse/apercu/")
        self.assertEqual(preview.status_code, 200)
        preview_lines = {
            line["mode_paiement"]: line for line in preview.data["lignes"]
        }
        self.assertEqual(preview_lines["ESPECES"]["montant_rembourse"], "0.00")
        self.assertEqual(preview_lines["ESPECES"]["montant_theorique"], "2500.00")
        executed = self.execute_refund(refund.data["id"])
        self.assertEqual(executed.status_code, 200)
        preview = self.api_client.get("/api/clotures-caisse/apercu/")
        preview_lines = {
            line["mode_paiement"]: line for line in preview.data["lignes"]
        }
        self.assertEqual(preview_lines["ESPECES"]["montant_rembourse"], "500.00")
        self.assertEqual(preview_lines["ESPECES"]["montant_theorique"], "2000.00")

        closed = self.api_client.post(
            "/api/clotures-caisse/",
            {"comptage": {"ESPECES": "2400.00"}},
            format="json",
        )
        self.assertEqual(closed.status_code, 201)
        lines = {line["mode_paiement"]: line for line in closed.data["lignes"]}
        self.assertEqual(lines["ESPECES"]["montant_encaisse"], "2500.00")
        self.assertEqual(lines["ESPECES"]["montant_rembourse"], "500.00")
        self.assertEqual(lines["ESPECES"]["montant_theorique"], "2000.00")
        self.assertEqual(lines["ESPECES"]["montant_compte"], "2400.00")
        self.assertEqual(lines["ESPECES"]["ecart"], "400.00")
        self.assertTrue(self.api_client.get(
            "/api/clotures-caisse/apercu/"
        ).data["cloturee"])

        pending_refund = self.create_refund(
            payment,
            amount="1000.00",
            reason="Demande après clôture",
        )
        authorized_after_close = self.api_client.post(
            f"/api/remboursements/{pending_refund.data['id']}/approuver/"
        )
        self.assertEqual(authorized_after_close.status_code, 200)
        refund_after_close = self.execute_refund(pending_refund.data["id"])
        self.assertEqual(refund_after_close.status_code, 409)

        duplicate = self.api_client.post("/api/clotures-caisse/", {}, format="json")
        self.assertEqual(duplicate.status_code, 409)

        later_payment = self.create_payment(
            invoice,
            amount="100.00",
            key=str(uuid4()),
        )
        self.assertEqual(later_payment.status_code, 409)
        self.assertEqual(ClotureCaisse.objects.filter(date_cloture__isnull=False).count(), 1)
