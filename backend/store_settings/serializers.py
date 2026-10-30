from rest_framework import serializers
from .models import ConfigurationMagasin


class ConfigurationMagasinSerializer(serializers.ModelSerializer):
    class Meta:
        model = ConfigurationMagasin
        fields = [
            "id",
            "nom_magasin",
            "logo",
            "adresse",
            "telephone",
            "email",
            "pied_de_page",
            "date_modification",
        ]
        read_only_fields = ["id", "date_modification"]