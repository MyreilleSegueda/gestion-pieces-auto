from django.db import transaction
from rest_framework import serializers

from inventory.models import PieceDetachee

from .models import AchatFournisseur, Fournisseur, LigneAchatFournisseur


class FournisseurSerializer(serializers.ModelSerializer):
    class Meta:
        model = Fournisseur
        fields = "__all__"
        read_only_fields = ("id", "date_creation")


class LigneAchatFournisseurCreateSerializer(serializers.Serializer):
    piece = serializers.PrimaryKeyRelatedField(
        queryset=PieceDetachee.objects.filter(actif=True),
    )
    quantite = serializers.IntegerField(min_value=1)
    prix_unitaire = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        min_value=0,
    )


class AchatFournisseurCreateSerializer(serializers.Serializer):
    fournisseur = serializers.PrimaryKeyRelatedField(
        queryset=Fournisseur.objects.filter(actif=True),
    )
    lignes = LigneAchatFournisseurCreateSerializer(many=True, allow_empty=False)

    def validate_lignes(self, lines):
        pieces = [line["piece"].pk for line in lines]
        if len(pieces) != len(set(pieces)):
            raise serializers.ValidationError(
                "Une pièce ne peut apparaître qu'une fois dans un achat."
            )
        return lines

    @transaction.atomic
    def create(self, validated_data):
        lines = validated_data.pop("lignes")
        purchase = AchatFournisseur.objects.create(
            **validated_data,
            cree_par=self.context["request"].user,
        )
        LigneAchatFournisseur.objects.bulk_create([
            LigneAchatFournisseur(
                achat=purchase,
                piece=item["piece"],
                reference_piece=item["piece"].reference,
                designation=item["piece"].designation,
                quantite=item["quantite"],
                prix_unitaire=item["prix_unitaire"],
            )
            for item in lines
        ])
        return purchase


class LigneAchatFournisseurReadSerializer(serializers.ModelSerializer):
    total = serializers.SerializerMethodField()

    class Meta:
        model = LigneAchatFournisseur
        fields = [
            "id",
            "piece",
            "reference_piece",
            "designation",
            "quantite",
            "prix_unitaire",
            "total",
        ]

    def get_total(self, line):
        return str(line.quantite * line.prix_unitaire)


class AchatFournisseurSerializer(serializers.ModelSerializer):
    fournisseur_nom = serializers.CharField(source="fournisseur.nom", read_only=True)
    lignes = LigneAchatFournisseurReadSerializer(many=True, read_only=True)
    montant_total = serializers.DecimalField(
        max_digits=14,
        decimal_places=2,
        read_only=True,
    )
    cree_par_nom = serializers.SerializerMethodField()
    recu_par_nom = serializers.SerializerMethodField()

    class Meta:
        model = AchatFournisseur
        fields = [
            "id",
            "reference",
            "fournisseur",
            "fournisseur_nom",
            "statut",
            "lignes",
            "montant_total",
            "cree_par",
            "cree_par_nom",
            "recu_par",
            "recu_par_nom",
            "date_creation",
            "date_reception",
        ]
        read_only_fields = fields

    def get_cree_par_nom(self, purchase):
        if purchase.cree_par is None:
            return "Non renseigné"
        return purchase.cree_par.get_full_name() or purchase.cree_par.username

    def get_recu_par_nom(self, purchase):
        if purchase.recu_par is None:
            return None
        return purchase.recu_par.get_full_name() or purchase.recu_par.username
