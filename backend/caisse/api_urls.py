
from rest_framework.routers import DefaultRouter

from .api_views import EncaissementViewSet, FactureCaisseViewSet

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

urlpatterns = router.urls
