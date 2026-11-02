from PIL import Image, UnidentifiedImageError
from rest_framework import serializers

from .models import ConfigurationMagasin


MAX_LOGO_SIZE = 2 * 1024 * 1024
ALLOWED_LOGO_FORMATS = {"JPEG", "PNG", "WEBP"}


class ConfigurationMagasinSerializer(serializers.ModelSerializer):
    logo = serializers.ImageField(required=False, allow_null=False)

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

    def validate_logo(self, logo):
        if logo.size > MAX_LOGO_SIZE:
            raise serializers.ValidationError(
                "Le logo ne doit pas dépasser 2 Mo."
            )

        try:
            logo.seek(0)
            with Image.open(logo) as image:
                image_format = image.format
                width, height = image.size
                image.verify()
        except (
            UnidentifiedImageError,
            OSError,
            SyntaxError,
            Image.DecompressionBombError,
        ) as error:
            raise serializers.ValidationError(
                "Le fichier doit être une image valide."
            ) from error
        finally:
            logo.seek(0)

        if image_format not in ALLOWED_LOGO_FORMATS:
            raise serializers.ValidationError(
                "Formats autorisés : PNG, JPEG ou WebP."
            )
        if width * height > 20_000_000:
            raise serializers.ValidationError(
                "Les dimensions du logo sont trop importantes."
            )
        return logo