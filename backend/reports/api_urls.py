from django.urls import path

from .api_views import tableau_de_bord
from .exports import export_report

urlpatterns = [
    path("rapports/tableau-de-bord/", tableau_de_bord, name="tableau-de-bord"),
    path("rapports/export/<str:export_type>/", export_report, name="export-report"),
]
