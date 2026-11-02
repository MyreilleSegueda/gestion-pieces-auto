
from rest_framework import serializers

from .models import (
    ClotureCaisse,
    ClotureCaisseLigne,
    Encaissement,
    Remboursement,
)
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
    montant_remboursable = serializers.SerializerMethodField()
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
            "montant_remboursable",
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

    def get_montant_remboursable(self, obj):
        rembourse = sum(
            (
                refund.montant
                for refund in obj.remboursements.all()
                if refund.statut != Remboursement.REFUSE
            ),
            start=Decimal("0.00"),
        )
        return str(max(obj.montant - rembourse, Decimal("0.00")))

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
    montant_encaisse_brut = serializers.DecimalField(
        source="total_encaisse",
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

    class Meta:
        model = Facture
        fields = [
            "id",
            "facture_reference",
            "vente_reference",
            "client_nom",
            "date_emission",
            "total_facture",
            "montant_encaisse_brut",
            "montant_avoirs",
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
        solde = obj.total - (
            obj.total_avoirs + obj.total_encaisse - obj.total_rembourse
        )
        if obj.vente.statut == "ANNULEE":
            return "0.00"
        return str(max(solde, Decimal("0.00")))

    def get_total_encaisse(self, obj):
        return str(max(obj.total_encaisse - obj.total_rembourse, Decimal("0.00")))

    def get_etat_paiement(self, obj):
        if obj.vente.statut == "ANNULEE":
            return "Annulée"
        encaisse = max(obj.total_encaisse - obj.total_rembourse, Decimal("0.00"))
        remaining_to_pay = max(obj.total - obj.total_avoirs, Decimal("0.00"))

        if remaining_to_pay == 0:
            if encaisse > 0:
                return "Régularisation requise"
            return "Remboursée" if obj.total_rembourse > 0 else "Soldée par avoir"
        if encaisse <= 0:
            return "Impayée"
        if encaisse < remaining_to_pay:
            return "Partiellement payée"
        return "Payée"


class RemboursementSerializer(serializers.ModelSerializer):
    encaissement_reference = serializers.CharField(
        source="encaissement.reference",
        read_only=True,
    )
    facture_reference = serializers.CharField(
        source="encaissement.facture.reference",
        read_only=True,
    )
    client_nom = serializers.SerializerMethodField()
    mode_paiement = serializers.CharField(
        source="encaissement.get_mode_paiement_display",
        read_only=True,
    )
    mode_remboursement_libelle = serializers.CharField(
        source="get_mode_remboursement_display",
        read_only=True,
    )
    demande_par_nom = serializers.SerializerMethodField()
    decide_par_nom = serializers.SerializerMethodField()
    execute_par_nom = serializers.SerializerMethodField()

    class Meta:
        model = Remboursement
        fields = [
            "id",
            "reference",
            "encaissement",
            "encaissement_reference",
            "facture_reference",
            "client_nom",
            "mode_paiement",
            "montant",
            "motif",
            "mode_remboursement",
            "mode_remboursement_libelle",
            "reference_execution",
            "statut",
            "demande_par",
            "demande_par_nom",
            "decide_par",
            "decide_par_nom",
            "execute_par",
            "execute_par_nom",
            "date_demande",
            "date_decision",
            "date_execution",
            "retour_vente",
        ]
        read_only_fields = fields

    def get_client_nom(self, obj):
        client = obj.encaissement.facture.vente.client
        return str(client) if client is not None else "Client comptoir"

    def get_demande_par_nom(self, obj):
        user = obj.demande_par
        if user is None:
            return "Utilisateur supprimé"
        return user.get_full_name() or user.username

    def get_decide_par_nom(self, obj):
        user = obj.decide_par
        if user is None:
            return None
        return user.get_full_name() or user.username

    def get_execute_par_nom(self, obj):
        user = obj.execute_par
        if user is None:
            return None
        return user.get_full_name() or user.username


class RemboursementCreateSerializer(serializers.Serializer):
    encaissement_id = serializers.IntegerField(min_value=1)
    montant = serializers.DecimalField(
        max_digits=14,
        decimal_places=2,
        min_value=Decimal("0.01"),
    )
    motif = serializers.CharField(max_length=1000, trim_whitespace=True)
    mode_remboursement = serializers.ChoiceField(
        choices=Encaissement.MODES_PAIEMENT,
        required=False,
    )

    def validate_motif(self, value):
        if not value:
            raise serializers.ValidationError("Le motif est obligatoire.")
        return value


class ClotureCaisseLigneSerializer(serializers.ModelSerializer):
    mode_paiement_libelle = serializers.CharField(
        source="get_mode_paiement_display",
        read_only=True,
    )
    ecart = serializers.SerializerMethodField()

    class Meta:
        model = ClotureCaisseLigne
        fields = [
            "mode_paiement",
            "mode_paiement_libelle",
            "montant_encaisse",
            "montant_rembourse",
            "montant_theorique",
            "montant_compte",
            "ecart",
        ]

    def get_ecart(self, obj):
        return None if obj.ecart is None else str(obj.ecart)


class ClotureCaisseSerializer(serializers.ModelSerializer):
    cloturee_par_nom = serializers.SerializerMethodField()
    lignes = ClotureCaisseLigneSerializer(many=True, read_only=True)

    class Meta:
        model = ClotureCaisse
        fields = [
            "id",
            "date_jour",
            "date_cloture",
            "cloturee_par",
            "cloturee_par_nom",
            "lignes",
        ]

    def get_cloturee_par_nom(self, obj):
        user = obj.cloturee_par
        if user is None:
            return "Utilisateur supprimé"
        return user.get_full_name() or user.username


class ClotureCaisseCreateSerializer(serializers.Serializer):
    comptage = serializers.DictField(
        child=serializers.DecimalField(
            max_digits=14,
            decimal_places=2,
            min_value=Decimal("0.00"),
        ),
        required=False,
    )

    def validate_comptage(self, value):
        allowed_modes = {mode for mode, _label in Encaissement.MODES_PAIEMENT}
        unknown_modes = set(value) - allowed_modes
        if unknown_modes:
            raise serializers.ValidationError(
                f"Modes de paiement inconnus : {', '.join(sorted(unknown_modes))}."
            )
        return value
