import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from clients.models import Client
from inventory.models import PieceDetachee


def reference_vente():
    return f"VTE-{uuid.uuid4().hex[:12].upper()}"


class Vente(models.Model):
    STATUTS = [
        ("BROUILLON", "Brouillon"),
        ("VALIDEE", "Validée"),
        ("ANNULEE", "Annulée"),
    ]

    reference = models.CharField(max_length=20, unique=True, default=reference_vente)
    client = models.ForeignKey(
        Client,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ventes",
    )
    statut = models.CharField(max_length=20, choices=STATUTS, default="BROUILLON")
    creee_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="ventes_creees",
    )
    validee_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ventes_validees",
    )
    date_creation = models.DateTimeField(auto_now_add=True)
    date_validation = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-date_creation", "-id"]
        verbose_name = "Vente"
        verbose_name_plural = "Ventes"

    @property
    def total(self):
        return sum((line.total for line in self.lignes.all()), start=0)

    def __str__(self):
        return self.reference


class LigneVente(models.Model):
    vente = models.ForeignKey(Vente, on_delete=models.PROTECT, related_name="lignes")
    piece = models.ForeignKey(PieceDetachee, on_delete=models.PROTECT, related_name="lignes_vente")
    reference_piece = models.CharField(max_length=50)
    designation = models.CharField(max_length=200)
    quantite = models.PositiveIntegerField()
    prix_unitaire = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        verbose_name = "Ligne de vente"
        verbose_name_plural = "Lignes de vente"

    def clean(self):
        super().clean()
        if self.prix_unitaire is not None and self.prix_unitaire < 0:
            raise ValidationError({
                "prix_unitaire": "Le prix de vente ne peut pas être négatif."
            })

    @property
    def total(self):
        return self.quantite * self.prix_unitaire

    def __str__(self):
        return f"{self.vente.reference} - {self.reference_piece}"
