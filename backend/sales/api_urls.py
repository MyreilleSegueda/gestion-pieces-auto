from rest_framework.routers import DefaultRouter

from .api_views import RetourVenteViewSet, VenteViewSet

router = DefaultRouter()
router.register("ventes", VenteViewSet, basename="vente")
router.register("retours-ventes", RetourVenteViewSet, basename="retour-vente")

urlpatterns = router.urls
