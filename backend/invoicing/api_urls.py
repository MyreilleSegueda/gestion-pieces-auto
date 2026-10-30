from rest_framework.routers import DefaultRouter

from .api_views import FactureViewSet

router = DefaultRouter()
router.register("factures", FactureViewSet, basename="facture")

urlpatterns = router.urls
