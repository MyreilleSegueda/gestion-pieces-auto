
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from rest_framework.test import APIClient

from inventory.models import Categorie, PieceDetachee
from invoicing.models import Facture


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

