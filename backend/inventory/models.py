
from django.db import models, transaction
from django.core.exceptions import ValidationError
from django.conf import settings
import uuid


class Categorie(models.Model):
    nom = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)

    class Meta:
        verbose_name = "Catégorie"
        verbose_name_plural = "Catégories"
        ordering = ["nom"]

    def __str__(self):
        return self.nom


class PieceDetachee(models.Model):
    reference = models.CharField(max_length=50, unique=True)
    designation = models.CharField(max_length=200)
    categorie = models.ForeignKey(
        Categorie,
        on_delete=models.PROTECT,
        related_name="pieces",
    )
    marque = models.CharField(max_length=100, blank=True)
    modeles_compatibles = models.TextField(blank=True)
    unite = models.CharField(max_length=30, default="unité")
    prix_achat = models.DecimalField(max_digits=12, decimal_places=2)
    prix_vente = models.DecimalField(max_digits=12, decimal_places=2)
    quantite_stock = models.PositiveIntegerField(default=0)
    seuil_minimal = models.PositiveIntegerField(default=0)
    emplacement = models.CharField(max_length=100, blank=True)
    actif = models.BooleanField(default=True)
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Pièce détachée"
        verbose_name_plural = "Pièces détachées"
        ordering = ["designation"]

    def clean(self):
        super().clean()
        errors = {}
        if self.prix_achat is not None and self.prix_achat < 0:
            errors["prix_achat"] = "Le prix d'achat ne peut pas être négatif."
        if self.prix_vente is not None and self.prix_vente < 0:
            errors["prix_vente"] = "Le prix de vente ne peut pas être négatif."
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f"{self.reference} - {self.designation}"

    @property
    def stock_faible(self):
        return 0 < self.quantite_stock <= self.seuil_minimal

    @property
    def en_rupture(self):
        return self.quantite_stock == 0


class MouvementStock(models.Model):
    TYPES_MOUVEMENT = [
        ("ENTREE", "Entrée"),
        ("SORTIE", "Sortie"),
        ("CORRECTION", "Correction d'inventaire"),
        ("RETOUR", "Retour"),
    ]

    piece = models.ForeignKey(
        PieceDetachee,
        on_delete=models.PROTECT,
        related_name="mouvements",
    )
    type_mouvement = models.CharField(
        max_length=20,
        choices=TYPES_MOUVEMENT,
    )
    quantite = models.PositiveIntegerField()
    prix_unitaire = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
    )
    motif = models.CharField(max_length=255)
    reference_document = models.CharField(
        max_length=100,
        blank=True,
    )
    date_mouvement = models.DateTimeField(auto_now_add=True)
    observation = models.TextField(blank=True)
    utilisateur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="mouvements_stock",
    )
    idempotency_key = models.UUIDField(
        unique=True,
        null=True,
        blank=True,
    )

    class Meta:
        verbose_name = "Mouvement de stock"
        verbose_name_plural = "Mouvements de stock"
        ordering = ["-date_mouvement"]

    def clean(self):
        super().clean()

        quantite_invalide = (
            self.quantite is None
            or self.quantite < 0
            or (self.quantite == 0 and self.type_mouvement != "CORRECTION")
        )
        if quantite_invalide:
            raise ValidationError({
                "quantite": (
                    "La quantité doit être positive, sauf pour une correction "
                    "qui peut définir le stock à zéro."
                )
            })

        if self.prix_unitaire is not None and self.prix_unitaire < 0:
            raise ValidationError({
                "prix_unitaire": "Le prix unitaire ne peut pas être négatif."
            })

        if self.pk:
            raise ValidationError(
                "Un mouvement enregistré ne peut pas être modifié. "
                "Créez un nouveau mouvement si une correction est nécessaire."
            )

        if self.piece_id and self.type_mouvement == "SORTIE":
            piece = PieceDetachee.objects.get(pk=self.piece_id)
            if self.quantite > piece.quantite_stock:
                raise ValidationError({
                    "quantite": (
                        f"Stock insuffisant : {piece.quantite_stock} "
                        "pièce(s) disponible(s)."
                    )
                })

    def save(self, *args, **kwargs):
        if self.pk is not None:
            raise ValidationError(
                "Un mouvement enregistré ne peut pas être modifié."
            )

        with transaction.atomic():
            piece = (
                PieceDetachee.objects
                .select_for_update()
                .get(pk=self.piece_id)
            )

            # Revalider le stock au moment de l'enregistrement
            # pour éviter une sortie supérieure au stock disponible.
            quantite_invalide = (
                self.quantite is None
                or self.quantite < 0
                or (self.quantite == 0 and self.type_mouvement != "CORRECTION")
            )
            if quantite_invalide:
                raise ValidationError(
                    "La quantité doit être positive, sauf pour une correction "
                    "qui peut définir le stock à zéro."
                )

            if self.prix_unitaire < 0:
                raise ValidationError(
                    "Le prix unitaire ne peut pas être négatif."
                )

            stock_actuel = piece.quantite_stock

            if self.type_mouvement == "ENTREE":
                nouveau_stock = stock_actuel + self.quantite

            elif self.type_mouvement == "SORTIE":
                if self.quantite > stock_actuel:
                    raise ValidationError(
                        f"Stock insuffisant : {stock_actuel} "
                        "pièce(s) disponible(s)."
                    )
                nouveau_stock = stock_actuel - self.quantite

            elif self.type_mouvement == "RETOUR":
                nouveau_stock = stock_actuel + self.quantite

            elif self.type_mouvement == "CORRECTION":
                nouveau_stock = self.quantite

            else:
                raise ValidationError("Type de mouvement non reconnu.")

            piece.quantite_stock = nouveau_stock
            piece.save(update_fields=[
                "quantite_stock",
                "date_modification",
            ])

            super().save(*args, **kwargs)

    def __str__(self):
        return (
            f"{self.get_type_mouvement_display()} - "
            f"{self.piece.reference} - {self.quantite}"
        )
