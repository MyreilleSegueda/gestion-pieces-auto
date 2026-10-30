
from rest_framework.routers import DefaultRouter
from .api_views import RoleViewSet, UtilisateurViewSet

router = DefaultRouter()
router.register("roles", RoleViewSet, basename="role")
router.register("utilisateurs", UtilisateurViewSet, basename="utilisateur")

urlpatterns = router.urls
