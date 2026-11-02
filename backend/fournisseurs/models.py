import uuid
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from inventory.models import PieceDetachee


def reference_achat():
    return f"ACH-{uuid.uuid4().hex[:12].upper()}"


class Fournisseur(models.Model):
    nom = models.CharField(max_length=200)
    telephone = models.CharField(max_length=30, blank=True)
    email = models.EmailField(blank=True)
    adresse = models.TextField(blank=True)
    actif = models.BooleanField(default=True)
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["nom", "id"]
        verbose_name = "Fournisseur"
        verbose_name_plural = "Fournisseurs"

    def __str__(self):
        return self.nom


class AchatFournisseur(models.Model):
    BROUILLON = "BROUILLON"
    RECU = "RECU"
    STATUTS = [
        (BROUILLON, "En attente de réception"),
        (RECU, "Réceptionné"),
    ]

    reference = models.CharField(
        max_length=24,
        unique=True,
        default=reference_achat,
    )
    fournisseur = models.ForeignKey(
        Fournisseur,
        on_delete=models.PROTECT,
        related_name="achats",
    )
    statut = models.CharField(max_length=20, choices=STATUTS, default=BROUILLON)
    cree_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="achats_fournisseurs_crees",
    )
    recu_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="achats_fournisseurs_recus",
    )
    date_creation = models.DateTimeField(auto_now_add=True)
    date_reception = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-date_creation", "-id"]
        verbose_name = "Achat fournisseur"
        verbose_name_plural = "Achats fournisseurs"

    @property
    def montant_total(self):
        return sum(
            (line.quantite * line.prix_unitaire for line in self.lignes.all()),
            start=Decimal("0.00"),
        )

    def __str__(self):
        return self.reference


class LigneAchatFournisseur(models.Model):
    achat = models.ForeignKey(
        AchatFournisseur,
        on_delete=models.PROTECT,
        related_name="lignes",
    )
    piece = models.ForeignKey(PieceDetachee, on_delete=models.PROTECT)
    reference_piece = models.CharField(max_length=50)
    designation = models.CharField(max_length=200)
    quantite = models.PositiveIntegerField()
    prix_unitaire = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["achat", "piece"],
                name="fournisseurs_achat_piece_unique",
            ),
            models.CheckConstraint(
                condition=models.Q(quantite__gt=0),
                name="fournisseurs_achat_quantite_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(prix_unitaire__gte=0),
                name="fournisseurs_achat_prix_nonnegative",
            ),
        ]
        verbose_name = "Ligne d'achat fournisseur"
        verbose_name_plural = "Lignes d'achat fournisseur"

    def clean(self):
        super().clean()
        if self.achat_id and self.achat.statut == AchatFournisseur.RECU:
            raise ValidationError("Un achat réceptionné ne peut plus être modifié.")

    def save(self, *args, **kwargs):
        if self.pk and self.achat.statut == AchatFournisseur.RECU:
            raise ValidationError("Un achat réceptionné ne peut plus être modifié.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.achat.statut == AchatFournisseur.RECU:
            raise ValidationError("Une ligne d'achat réceptionnée ne peut pas être supprimée.")
        return super().delete(*args, **kwargs)
