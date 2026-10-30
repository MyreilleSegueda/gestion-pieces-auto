
from rest_framework.routers import DefaultRouter
from .api_views import (
    CategorieViewSet,
    PieceDetacheeViewSet,
    MouvementStockViewSet,
)

router = DefaultRouter()
router.register("categories", CategorieViewSet, basename="categorie")
router.register("pieces", PieceDetacheeViewSet, basename="piece")
router.register("mouvements", MouvementStockViewSet, basename="mouvement")

urlpatterns = router.urls
