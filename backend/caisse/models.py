
import uuid

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone
from decimal import Decimal


def reference_encaissement():
    return f"ENC-{uuid.uuid4().hex[:12].upper()}"


def reference_remboursement():
    return f"RMB-{uuid.uuid4().hex[:12].upper()}"


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
    idempotency_key = models.UUIDField(
        unique=True,
        null=True,
        blank=True,
        editable=False,
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


class Remboursement(models.Model):
    EN_ATTENTE = "EN_ATTENTE"
    AUTORISE = "AUTORISE"
    REFUSE = "REFUSE"
    EXECUTE = "EXECUTE"
    STATUTS = [
        (EN_ATTENTE, "En attente"),
        (AUTORISE, "Autorisé"),
        (REFUSE, "Refusé"),
        (EXECUTE, "Exécuté"),
    ]

    reference = models.CharField(
        max_length=20,
        unique=True,
        default=reference_remboursement,
    )
    idempotency_key = models.UUIDField(
        unique=True,
        null=True,
        blank=True,
        editable=False,
    )
    encaissement = models.ForeignKey(
        Encaissement,
        on_delete=models.PROTECT,
        related_name="remboursements",
    )
    montant = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    motif = models.TextField()
    mode_remboursement = models.CharField(
        max_length=20,
        choices=Encaissement.MODES_PAIEMENT,
    )
    reference_execution = models.CharField(max_length=100, blank=True)
    statut = models.CharField(max_length=20, choices=STATUTS, default=EN_ATTENTE)
    demande_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="remboursements_demandes",
    )
    decide_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="remboursements_decides",
    )
    execute_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="remboursements_executes",
    )
    date_demande = models.DateTimeField(auto_now_add=True)
    date_decision = models.DateTimeField(null=True, blank=True)
    date_execution = models.DateTimeField(null=True, blank=True)
    retour_vente = models.ForeignKey(
        "sales.RetourVente",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="remboursements",
    )

    class Meta:
        ordering = ["-date_demande", "-id"]
        verbose_name = "Remboursement"
        verbose_name_plural = "Remboursements"
        constraints = [
            models.UniqueConstraint(
                fields=["retour_vente", "encaissement"],
                condition=models.Q(retour_vente__isnull=False),
                name="caisse_remboursement_retour_paiement_unique",
            ),
            models.CheckConstraint(
                condition=models.Q(montant__gt=0),
                name="caisse_remboursement_montant_positif",
            ),
        ]

    def __str__(self):
        return f"{self.reference} - {self.montant}"


class ClotureCaisse(models.Model):
    date_jour = models.DateField(unique=True)
    cloturee_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="clotures_caisse",
    )
    date_cloture = models.DateTimeField(null=True, blank=True)
    creee_le = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date_jour"]
        verbose_name = "Journée de caisse"
        verbose_name_plural = "Journées de caisse"

    @property
    def est_cloturee(self):
        return self.date_cloture is not None

    def __str__(self):
        return f"Caisse du {self.date_jour}"


class ClotureCaisseLigne(models.Model):
    cloture = models.ForeignKey(
        ClotureCaisse,
        on_delete=models.PROTECT,
        related_name="lignes",
    )
    mode_paiement = models.CharField(
        max_length=20,
        choices=Encaissement.MODES_PAIEMENT,
    )
    montant_encaisse = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    montant_rembourse = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    montant_theorique = models.DecimalField(max_digits=14, decimal_places=2)
    montant_compte = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0.00"))],
    )

    class Meta:
        ordering = ["mode_paiement"]
        verbose_name = "Détail de clôture de caisse"
        verbose_name_plural = "Détails de clôture de caisse"
        constraints = [
            models.UniqueConstraint(
                fields=["cloture", "mode_paiement"],
                name="caisse_cloture_mode_unique",
            ),
            models.CheckConstraint(
                condition=models.Q(montant_compte__isnull=True)
                | models.Q(montant_compte__gte=0),
                name="caisse_cloture_comptage_non_negatif",
            ),
        ]

    @property
    def ecart(self):
        if self.montant_compte is None:
            return None
        return self.montant_compte - self.montant_theorique
