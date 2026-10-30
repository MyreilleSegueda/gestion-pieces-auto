from rest_framework import serializers

from sales.serializers import LigneVenteReadSerializer

from .models import Facture


class FactureSerializer(serializers.ModelSerializer):
    vente_reference = serializers.CharField(source="vente.reference", read_only=True)
    client_nom = serializers.CharField(
        source="vente.client.nom",
        read_only=True,
        allow_null=True,
    )
    lignes = LigneVenteReadSerializer(source="vente.lignes", many=True, read_only=True)
    total = serializers.DecimalField(max_digits=14, decimal_places=2, read_only=True)
    emise_par_nom = serializers.SerializerMethodField()

    def get_emise_par_nom(self, invoice):
        if invoice.emise_par is None:
            return "Non renseigné"
        return invoice.emise_par.get_full_name() or invoice.emise_par.username

    class Meta:
        model = Facture
        fields = "__all__"
        read_only_fields = ("id", "reference", "vente", "emise_par", "date_emission")
