

from django.contrib import admin
from .models import Categorie, PieceDetachee, MouvementStock


@admin.register(Categorie)
class CategorieAdmin(admin.ModelAdmin):
    list_display = ("id", "nom")
    search_fields = ("nom",)



@admin.register(PieceDetachee)
class PieceDetacheeAdmin(admin.ModelAdmin):
    list_display = (
        "reference",
        "designation",
        "categorie",
        "prix_achat",
        "prix_vente",
        "quantite_stock",
        "seuil_minimal",
        "stock_faible",
        "en_rupture",
        "actif",
    )
    search_fields = ("reference", "designation", "marque")
    list_filter = ("categorie", "actif")
    list_editable = ("actif",)
    readonly_fields = ("quantite_stock",)



@admin.register(MouvementStock)
class MouvementStockAdmin(admin.ModelAdmin):
    list_display = (
        "date_mouvement",
        "piece",
        "type_mouvement",
        "quantite",
        "prix_unitaire",
        "motif",
    )
    search_fields = (
        "piece__reference",
        "piece__designation",
        "motif",
        "reference_document",
    )
    list_filter = ("type_mouvement", "date_mouvement")
    readonly_fields = ("date_mouvement", "utilisateur")

    def save_model(self, request, obj, form, change):
        if not change:
            obj.utilisateur = request.user
        super().save_model(request, obj, form, change)



    def has_delete_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        if obj is not None:
            return False
        return super().has_change_permission(request, obj)

