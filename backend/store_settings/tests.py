from io import BytesIO
from tempfile import TemporaryDirectory

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from PIL import Image
from rest_framework.test import APIClient

from .models import ConfigurationMagasin


class ConfigurationMagasinApiTests(TestCase):
    def setUp(self):
        self.api_client = APIClient()
        self.admin = get_user_model().objects.create_user(
            username="store-admin",
            password="test-password",
        )
        admin_group, _ = Group.objects.get_or_create(name="Administrateur")
        self.admin.groups.add(admin_group)
        self.reader = get_user_model().objects.create_user(
            username="store-reader",
            password="test-password",
        )

    def valid_png(self):
        output = BytesIO()
        Image.new("RGB", (2, 2), color="blue").save(output, format="PNG")
        return SimpleUploadedFile(
            "logo.png",
            output.getvalue(),
            content_type="image/png",
        )

    def test_authenticated_reader_can_read_but_not_modify(self):
        self.api_client.force_authenticate(self.reader)

        self.assertEqual(self.api_client.get("/api/store-settings/").status_code, 200)
        response = self.api_client.patch(
            "/api/store-settings/",
            {"nom_magasin": "Nom non autorisé"},
        )

        self.assertEqual(response.status_code, 403)
        self.assertNotEqual(
            ConfigurationMagasin.objects.get(pk=1).nom_magasin,
            "Nom non autorisé",
        )

    def test_admin_can_upload_logo_and_patch_without_replacing_it(self):
        with TemporaryDirectory() as media_root, override_settings(
            MEDIA_ROOT=media_root
        ):
            self.api_client.force_authenticate(self.admin)
            uploaded = self.api_client.patch(
                "/api/store-settings/",
                {
                    "nom_magasin": "Garage Central",
                    "logo": self.valid_png(),
                },
                format="multipart",
            )

            self.assertEqual(uploaded.status_code, 200, uploaded.data)
            logo_name = uploaded.data["logo"].split("/")[-1]
            config = ConfigurationMagasin.objects.get(pk=1)
            self.assertTrue(config.logo.storage.exists(config.logo.name))

            updated = self.api_client.patch(
                "/api/store-settings/",
                {"adresse": "Centre-ville"},
                format="multipart",
            )

            self.assertEqual(updated.status_code, 200, updated.data)
            config.refresh_from_db()
            self.assertEqual(config.logo.name.split("/")[-1], logo_name)
            self.assertEqual(config.nom_magasin, "Garage Central")
            self.assertEqual(config.adresse, "Centre-ville")

    def test_invalid_or_oversized_logo_is_rejected(self):
        self.api_client.force_authenticate(self.admin)

        invalid = self.api_client.patch(
            "/api/store-settings/",
            {
                "logo": SimpleUploadedFile(
                    "fake.png",
                    b"not an image",
                    content_type="image/png",
                )
            },
            format="multipart",
        )
        oversized = self.api_client.patch(
            "/api/store-settings/",
            {
                "logo": SimpleUploadedFile(
                    "large.png",
                    b"x" * (2 * 1024 * 1024 + 1),
                    content_type="image/png",
                )
            },
            format="multipart",
        )

        self.assertEqual(invalid.status_code, 400)
        self.assertEqual(oversized.status_code, 400)
