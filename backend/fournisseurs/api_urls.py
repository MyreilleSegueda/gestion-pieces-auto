from rest_framework.routers import DefaultRouter

from .api_views import FournisseurViewSet

router = DefaultRouter()
router.register("fournisseurs", FournisseurViewSet, basename="fournisseur")

urlpatterns = router.urls
