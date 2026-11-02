from rest_framework.routers import DefaultRouter

from .api_views import AchatFournisseurViewSet, FournisseurViewSet

router = DefaultRouter()
router.register("fournisseurs", FournisseurViewSet, basename="fournisseur")
router.register(
    "achats-fournisseurs",
    AchatFournisseurViewSet,
    basename="achat-fournisseur",
)

urlpatterns = router.urls
