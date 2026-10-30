from django.urls import path

from .api_views import tableau_de_bord

urlpatterns = [
    path("rapports/tableau-de-bord/", tableau_de_bord, name="tableau-de-bord"),
]
