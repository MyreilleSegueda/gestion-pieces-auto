
from rest_framework.routers import DefaultRouter

from .api_views import (
    ClotureCaisseViewSet,
    EncaissementViewSet,
    FactureCaisseViewSet,
    RemboursementViewSet,
)

router = DefaultRouter()

router.register(
    "encaissements",
    EncaissementViewSet,
    basename="encaissement",
)

router.register(
    "factures-a-encaisser",
    FactureCaisseViewSet,
    basename="facture-caisse",
)

router.register(
    "remboursements",
    RemboursementViewSet,
    basename="remboursement",
)

router.register(
    "clotures-caisse",
    ClotureCaisseViewSet,
    basename="cloture-caisse",
)

urlpatterns = router.urls
