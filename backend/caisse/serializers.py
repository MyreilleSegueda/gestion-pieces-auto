
from rest_framework import serializers

from .models import Encaissement
from invoicing.models import Facture
from decimal import Decimal



class EncaissementSerializer(serializers.ModelSerializer):
    facture_reference = serializers.CharField(
        source="facture.reference",
        read_only=True,
    )
    facture_total = serializers.DecimalField(
        source="facture.total",
        max_digits=14,
        decimal_places=2,
        read_only=True,
    )
    client_nom = serializers.SerializerMethodField()
    mode_paiement_libelle = serializers.CharField(
        source="get_mode_paiement_display",
        read_only=True,
    )
    encaisse_par_nom = serializers.SerializerMethodField()

    class Meta:
        model = Encaissement
        fields = [
            "id",
            "reference",
            "facture",
            "facture_reference",
            "facture_total",
            "client_nom",
            "montant",
            "mode_paiement",
            "mode_paiement_libelle",
            "date_encaissement",
            "encaisse_par",
            "encaisse_par_nom",
        ]
        read_only_fields = [
            "id",
            "reference",
            "date_encaissement",
            "encaisse_par",
        ]

    def get_client_nom(self, obj):
        client = obj.facture.vente.client
        if client is None:
            return "Client comptoir"
        return str(client)

    def get_encaisse_par_nom(self, obj):
        user = obj.encaisse_par
        if user is None:
            return "Utilisateur supprimé"
        return user.get_full_name() or user.username


class EncaissementCreateSerializer(serializers.Serializer):
    facture_id = serializers.IntegerField(min_value=1)
    montant = serializers.DecimalField(
        max_digits=14,
        decimal_places=2,
        min_value=Decimal("0.01"),
    )
    mode_paiement = serializers.ChoiceField(
        choices=Encaissement.MODES_PAIEMENT,
    )

class FactureCaisseSerializer(serializers.ModelSerializer):
    facture_reference = serializers.CharField(
        source="reference",
        read_only=True,
    )
    vente_reference = serializers.CharField(
        source="vente.reference",
        read_only=True,
    )
    client_nom = serializers.SerializerMethodField()
    total_facture = serializers.DecimalField(
        source="total",
        max_digits=14,
        decimal_places=2,
        read_only=True,
    )
    total_encaisse = serializers.DecimalField(
        max_digits=14,
        decimal_places=2,
        read_only=True,
    )
    solde_restant = serializers.SerializerMethodField()
    etat_paiement = serializers.SerializerMethodField()

    class Meta:
        model = Facture
        fields = [
            "id",
            "facture_reference",
            "vente_reference",
            "client_nom",
            "date_emission",
            "total_facture",
            "total_encaisse",
            "solde_restant",
            "etat_paiement",
        ]

    def get_client_nom(self, obj):
        client = obj.vente.client
        if client is None:
            return "Client comptoir"
        return str(client)

    def get_solde_restant(self, obj):
        from decimal import Decimal

        solde = obj.total - obj.total_encaisse
        return str(max(solde, Decimal("0.00")))

    def get_etat_paiement(self, obj):
        total = obj.total
        encaisse = obj.total_encaisse

        if encaisse <= 0:
            return "Impayée"
        if encaisse < total:
            return "Partiellement payée"
        return "Payée"
