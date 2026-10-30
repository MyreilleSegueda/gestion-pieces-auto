from django.urls import path
from .api_views import ConfigurationMagasinAPIView

urlpatterns = [
    path(
        "",
        ConfigurationMagasinAPIView.as_view(),
        name="configuration-magasin"
    ),
]