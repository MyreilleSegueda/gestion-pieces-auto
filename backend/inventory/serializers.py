
from rest_framework import serializers
from .models import Categorie, PieceDetachee, MouvementStock


class CategorieSerializer(serializers.ModelSerializer):
    class Meta:
        model = Categorie
        fields = "__all__"


class PieceDetacheeSerializer(serializers.ModelSerializer):
    categorie_nom = serializers.CharField(
        source="categorie.nom",
        read_only=True
    )
    stock_faible = serializers.ReadOnlyField()
    en_rupture = serializers.ReadOnlyField()

    def validate_prix_achat(self, value):
        if value < 0:
            raise serializers.ValidationError(
                "Le prix d'achat ne peut pas être négatif."
            )
        return value

    def validate_prix_vente(self, value):
        if value < 0:
            raise serializers.ValidationError(
                "Le prix de vente ne peut pas être négatif."
            )
        return value

    class Meta:
        model = PieceDetachee
        fields = "__all__"
        read_only_fields = ("quantite_stock", "date_creation", "date_modification")


class MouvementStockSerializer(serializers.ModelSerializer):
    piece_reference = serializers.CharField(
        source="piece.reference",
        read_only=True
    )
    piece_designation = serializers.CharField(
        source="piece.designation",
        read_only=True
    )
    utilisateur_nom = serializers.SerializerMethodField()

    def get_utilisateur_nom(self, movement):
        if movement.utilisateur is None:
            return "Non renseigné"
        return movement.utilisateur.get_full_name() or movement.utilisateur.username

    class Meta:
        model = MouvementStock
        fields = "__all__"
        read_only_fields = ("date_mouvement", "utilisateur", "idempotency_key")

