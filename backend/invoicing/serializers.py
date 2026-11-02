from decimal import Decimal

from rest_framework import serializers

from caisse.models import Encaissement

from sales.serializers import LigneVenteReadSerializer

from .models import Facture


class HistoriqueEncaissementSerializer(serializers.ModelSerializer):
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
            "montant",
            "mode_paiement_libelle",
            "date_encaissement",
            "encaisse_par_nom",
        ]

    def get_encaisse_par_nom(self, obj):
        user = obj.encaisse_par
        if user is None:
            return "Utilisateur supprimé"
        return user.get_full_name() or user.username


class FactureSerializer(serializers.ModelSerializer):
    vente_reference = serializers.CharField(source="vente.reference", read_only=True)
    client_nom = serializers.CharField(
        source="vente.client.nom",
        read_only=True,
        allow_null=True,
    )
    lignes = LigneVenteReadSerializer(source="vente.lignes", many=True, read_only=True)
    total = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    montant_encaisse_brut = serializers.DecimalField(
        source="total_encaisse",
        max_digits=14,
        decimal_places=2,
        read_only=True,
    )
    montant_rembourse = serializers.DecimalField(
        source="total_rembourse",
        max_digits=14,
        decimal_places=2,
        read_only=True,
    )
    montant_avoirs = serializers.DecimalField(
        source="total_avoirs",
        max_digits=14,
        decimal_places=2,
        read_only=True,
    )
    total_encaisse = serializers.SerializerMethodField()
    solde_restant = serializers.SerializerMethodField()
    etat_paiement = serializers.SerializerMethodField()
    historique_encaissements = HistoriqueEncaissementSerializer(
        source="encaissements",
        many=True,
        read_only=True,
    )
    emise_par_nom = serializers.SerializerMethodField()

    def get_emise_par_nom(self, invoice):
        if invoice.emise_par is None:
            return "Non renseigné"
        return invoice.emise_par.get_full_name() or invoice.emise_par.username

    class Meta:
        model = Facture
        fields = [
            "id",
            "reference",
            "vente",
            "vente_reference",
            "client_nom",
            "lignes",
            "total",
            "montant_encaisse_brut",
            "montant_rembourse",
            "montant_avoirs",
            "total_encaisse",
            "solde_restant",
            "etat_paiement",
            "historique_encaissements",
            "emise_par",
            "emise_par_nom",
            "date_emission",
        ]
        read_only_fields = ("id", "reference", "vente", "emise_par", "date_emission")

    def get_total_encaisse(self, invoice):
        return str(max(invoice.total_encaisse - invoice.total_rembourse, Decimal("0.00")))

    def get_solde_restant(self, invoice):
        return str(
            max(
                invoice.total
                - invoice.total_avoirs
                - invoice.total_encaisse
                + invoice.total_rembourse,
                Decimal("0.00"),
            )
        )

    def get_etat_paiement(self, invoice):
        if invoice.vente.statut == "ANNULEE":
            return "Annulée"
        remaining_to_pay = max(
            invoice.total - invoice.total_avoirs,
            Decimal("0.00"),
        )
        net_paid = max(
            invoice.total_encaisse - invoice.total_rembourse,
            Decimal("0.00"),
        )
        if remaining_to_pay == 0:
            if net_paid > 0:
                return "Régularisation requise"
            return "Remboursée" if invoice.total_rembourse > 0 else "Soldée par avoir"
        if net_paid <= 0:
            return "Impayée"
        if net_paid < remaining_to_pay:
            return "Partiellement payée"
        return "Payée"
