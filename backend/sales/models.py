import uuid
from decimal import Decimal

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


class RetourVente(models.Model):
    RETOUR = "RETOUR"
    ANNULATION = "ANNULATION"
    TYPES = [
        (RETOUR, "Retour de pièces"),
        (ANNULATION, "Annulation de vente"),
    ]
    EN_ATTENTE = "EN_ATTENTE"
    AUTORISE = "AUTORISE"
    REFUSE = "REFUSE"
    STATUTS = [
        (EN_ATTENTE, "En attente"),
        (AUTORISE, "Autorisé"),
        (REFUSE, "Refusé"),
    ]

    reference = models.CharField(max_length=24, unique=True)
    vente = models.ForeignKey(
        Vente,
        on_delete=models.PROTECT,
        related_name="retours",
    )
    type_operation = models.CharField(max_length=20, choices=TYPES)
    motif = models.TextField()
    statut = models.CharField(
        max_length=20,
        choices=STATUTS,
        default=EN_ATTENTE,
    )
    remise_en_stock = models.BooleanField(default=False)
    idempotency_key = models.UUIDField(
        unique=True,
        null=True,
        blank=True,
        editable=False,
    )
    demande_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="retours_ventes_demandes",
    )
    autorise_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="retours_ventes_autorises",
    )
    date_demande = models.DateTimeField(auto_now_add=True)
    date_decision = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-date_demande", "-id"]
        verbose_name = "Retour ou annulation de vente"
        verbose_name_plural = "Retours et annulations de vente"
        constraints = [
            models.UniqueConstraint(
                fields=["vente"],
                condition=models.Q(type_operation="ANNULATION"),
                name="sales_vente_annulation_unique",
            ),
        ]

    @property
    def montant_total(self):
        return sum(
            (line.quantite * line.prix_unitaire for line in self.lignes.all()),
            start=Decimal("0.00"),
        )

    def __str__(self):
        return self.reference


class LigneRetourVente(models.Model):
    retour = models.ForeignKey(
        RetourVente,
        on_delete=models.PROTECT,
        related_name="lignes",
    )
    ligne_vente = models.ForeignKey(
        LigneVente,
        on_delete=models.PROTECT,
        related_name="retours",
    )
    reference_piece = models.CharField(max_length=50)
    designation = models.CharField(max_length=200)
    quantite = models.PositiveIntegerField()
    prix_unitaire = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        verbose_name = "Ligne de retour de vente"
        verbose_name_plural = "Lignes de retour de vente"
        constraints = [
            models.UniqueConstraint(
                fields=["retour", "ligne_vente"],
                name="sales_retour_ligne_unique",
            ),
            models.CheckConstraint(
                condition=models.Q(quantite__gt=0),
                name="sales_retour_quantite_positive",
            ),
        ]

    def __str__(self):
        return f"{self.retour.reference} - {self.reference_piece}"
