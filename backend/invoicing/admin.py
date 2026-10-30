from django.contrib import admin

from .models import Facture


@admin.register(Facture)
class FactureAdmin(admin.ModelAdmin):
    list_display = ("reference", "vente", "date_emission", "emise_par")
    search_fields = ("reference", "vente__reference")
    readonly_fields = ("reference", "vente", "emise_par", "date_emission")

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        if obj is not None:
            return False
        return super().has_change_permission(request, obj)
