
from django.contrib import admin
from django.urls import include, path
from django.conf import settings
from django.conf.urls.static import static
urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/auth/", include("accounts.urls")),
    path("api/", include("inventory.api_urls")),
    path("api/", include("utilisateurs.api_urls")),
    path("api/", include("clients.api_urls")),
    path("api/", include("fournisseurs.api_urls")),
    path("api/", include("sales.api_urls")),
    path("api/", include("invoicing.api_urls")),
    path("api/", include("reports.api_urls")),
    path("api/", include("caisse.api_urls")),
    path("api/store-settings/", include("store_settings.api_urls")),
]
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)