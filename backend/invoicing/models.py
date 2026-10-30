import uuid

from django.conf import settings
from django.db import models

from sales.models import Vente


def reference_facture():
    return f"FAC-{uuid.uuid4().hex[:12].upper()}"


class Facture(models.Model):
    reference = models.CharField(max_length=20, unique=True, default=reference_facture)
    vente = models.OneToOneField(
        Vente,
        on_delete=models.PROTECT,
        related_name="facture",
    )
    emise_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="factures_emises",
    )
    date_emission = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date_emission", "-id"]
        verbose_name = "Facture"
        verbose_name_plural = "Factures"

    @property
    def total(self):
        return self.vente.total

    def __str__(self):
        return self.reference
