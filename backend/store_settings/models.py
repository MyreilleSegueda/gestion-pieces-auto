from django.db import models


class ConfigurationMagasin(models.Model):
    nom_magasin = models.CharField(
        max_length=150,
        default="MAGASIN DE PIÈCES DÉTACHÉES AUTOMOBILES"
    )
    logo = models.ImageField(
        upload_to="store/logo/",
        blank=True,
        null=True
    )
    adresse = models.CharField(max_length=255, blank=True)
    telephone = models.CharField(max_length=30, blank=True)
    email = models.EmailField(blank=True)
    pied_de_page = models.TextField(blank=True)

    date_modification = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    def __str__(self):
        return self.nom_magasin