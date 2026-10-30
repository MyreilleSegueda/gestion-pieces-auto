from django.db import transaction
from rest_framework import serializers

from clients.models import Client
from inventory.models import PieceDetachee

from .models import LigneVente, Vente


class LigneVenteReadSerializer(serializers.ModelSerializer):
    total = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)

    class Meta:
        model = LigneVente
        fields = [
            "id",
            "piece",
            "reference_piece",
            "designation",
            "quantite",
            "prix_unitaire",
            "total",
        ]


class VenteSerializer(serializers.ModelSerializer):
    lignes = LigneVenteReadSerializer(many=True, read_only=True)
    total = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    client_nom = serializers.CharField(source="client.nom", read_only=True, allow_null=True)
    creee_par_nom = serializers.SerializerMethodField()

    def get_creee_par_nom(self, sale):
        if sale.creee_par is None:
            return "Non renseigné"
        return sale.creee_par.get_full_name() or sale.creee_par.username

    class Meta:
        model = Vente
        fields = "__all__"
        read_only_fields = (
            "id",
            "reference",
            "statut",
            "creee_par",
            "validee_par",
            "date_creation",
            "date_validation",
            "lignes",
            "total",
            "client_nom",
            "creee_par_nom",
        )


class LigneVenteCreateSerializer(serializers.Serializer):
    piece = serializers.PrimaryKeyRelatedField(queryset=PieceDetachee.objects.all())
    quantite = serializers.IntegerField(min_value=1)


class VenteCreateSerializer(serializers.Serializer):
    client = serializers.PrimaryKeyRelatedField(
        queryset=Client.objects.filter(actif=True),
        required=False,
        allow_null=True,
    )
    lignes = LigneVenteCreateSerializer(many=True, allow_empty=False)

    def validate_lignes(self, lines):
        piece_ids = [line["piece"].pk for line in lines]
        if len(piece_ids) != len(set(piece_ids)):
            raise serializers.ValidationError(
                "Une pièce ne peut apparaître qu'une fois dans une vente."
            )
        for line in lines:
            if not line["piece"].actif:
                raise serializers.ValidationError(
                    f"La pièce {line['piece'].reference} est désactivée."
                )
            if line["piece"].prix_vente < 0:
                raise serializers.ValidationError(
                    f"Le prix de vente de {line['piece'].reference} "
                    "ne peut pas être négatif."
                )
        return lines

    @transaction.atomic
    def create(self, validated_data):
        lines = validated_data.pop("lignes")
        sale = Vente.objects.create(**validated_data)
        LigneVente.objects.bulk_create([
            LigneVente(
                vente=sale,
                piece=line["piece"],
                reference_piece=line["piece"].reference,
                designation=line["piece"].designation,
                quantite=line["quantite"],
                prix_unitaire=line["piece"].prix_vente,
            )
            for line in lines
        ])
        return sale


class VenteDraftUpdateSerializer(serializers.Serializer):
    client = serializers.PrimaryKeyRelatedField(
        queryset=Client.objects.filter(actif=True),
        required=False,
        allow_null=True,
    )
    lignes = LigneVenteCreateSerializer(many=True, allow_empty=False, required=False)

    def validate_lignes(self, lines):
        piece_ids = [line["piece"].pk for line in lines]
        if len(piece_ids) != len(set(piece_ids)):
            raise serializers.ValidationError(
                "Une pièce ne peut apparaître qu'une fois dans une vente."
            )
        for line in lines:
            piece = line["piece"]
            if not piece.actif:
                raise serializers.ValidationError(
                    f"La pièce {piece.reference} est désactivée."
                )
            if piece.prix_vente < 0:
                raise serializers.ValidationError(
                    f"Le prix de vente de {piece.reference} ne peut pas être négatif."
                )
        return lines

    @transaction.atomic
    def update(self, instance, validated_data):
        if "client" in validated_data:
            instance.client = validated_data["client"]

        if "lignes" in validated_data:
            existing_lines = {
                line.piece_id: line
                for line in instance.lignes.select_related("piece").all()
            }
            retained_piece_ids = set()

            for item in validated_data["lignes"]:
                piece = item["piece"]
                existing_line = existing_lines.get(piece.pk)
                if existing_line is not None:
                    retained_piece_ids.add(piece.pk)
                    if existing_line.quantite != item["quantite"]:
                        existing_line.quantite = item["quantite"]
                        existing_line.save(update_fields=["quantite"])
                    continue

                LigneVente.objects.create(
                    vente=instance,
                    piece=piece,
                    reference_piece=piece.reference,
                    designation=piece.designation,
                    quantite=item["quantite"],
                    prix_unitaire=piece.prix_vente,
                )

            for piece_id, line in existing_lines.items():
                if piece_id not in retained_piece_ids:
                    line.delete()

        instance.save()
        return instance
