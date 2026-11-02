from django.contrib import admin

from .models import ClotureCaisse, ClotureCaisseLigne, Encaissement, Remboursement


@admin.register(Encaissement)
class EncaissementAdmin(admin.ModelAdmin):
    list_display = (
        "reference",
        "facture",
        "montant",
        "mode_paiement",
        "date_encaissement",
        "encaisse_par",
    )
    list_filter = ("mode_paiement", "date_encaissement")
    search_fields = ("reference", "facture__reference")
    readonly_fields = ("reference", "idempotency_key")


@admin.register(Remboursement)
class RemboursementAdmin(admin.ModelAdmin):
    list_display = (
        "reference",
        "encaissement",
        "montant",
        "statut",
        "demande_par",
        "decide_par",
        "date_demande",
    )
    list_filter = ("statut", "date_demande", "date_decision")
    search_fields = ("reference", "encaissement__reference")
    readonly_fields = (
        "reference",
        "encaissement",
        "montant",
        "motif",
        "demande_par",
        "decide_par",
        "date_demande",
        "date_decision",
        "statut",
    )


class ClotureCaisseLigneInline(admin.TabularInline):
    model = ClotureCaisseLigne
    extra = 0
    can_delete = False
    readonly_fields = (
        "mode_paiement",
        "montant_theorique",
        "montant_compte",
    )


@admin.register(ClotureCaisse)
class ClotureCaisseAdmin(admin.ModelAdmin):
    list_display = ("date_jour", "date_cloture", "cloturee_par")
    readonly_fields = ("date_jour", "date_cloture", "cloturee_par")
    inlines = [ClotureCaisseLigneInline]
