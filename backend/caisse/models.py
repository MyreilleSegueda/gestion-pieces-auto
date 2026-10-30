
import uuid

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone
from decimal import Decimal


def reference_encaissement():
    return f"ENC-{uuid.uuid4().hex[:12].upper()}"


class Encaissement(models.Model):
    MODES_PAIEMENT = [
        ("ESPECES", "Espèces"),
        ("MOBILE_MONEY", "Mobile money"),
        ("CARTE", "Carte bancaire"),
        ("VIREMENT", "Virement"),
        ("AUTRE", "Autre"),
    ]

    reference = models.CharField(
        max_length=20,
        unique=True,
        default=reference_encaissement,
    )
    facture = models.ForeignKey(
        "invoicing.Facture",
        on_delete=models.PROTECT,
        related_name="encaissements",
    )
    montant = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))]
    )
    mode_paiement = models.CharField(
        max_length=20,
        choices=MODES_PAIEMENT,
    )
    date_encaissement = models.DateTimeField(default=timezone.now)
    encaisse_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="encaissements_enregistres",
    )

    class Meta:
        ordering = ["-date_encaissement", "-id"]
        verbose_name = "Encaissement"
        verbose_name_plural = "Encaissements"
        constraints = [
            models.CheckConstraint(
                condition=Q(montant__gt=0),
                name="caisse_encaissement_montant_positif",
            ),
        ]

    def __str__(self):
        return f"{self.reference} - {self.montant}"
