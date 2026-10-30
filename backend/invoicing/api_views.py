from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from .models import Facture
from .serializers import FactureSerializer


class FactureViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Facture.objects.select_related(
        "vente",
        "vente__client",
        "emise_par",
    ).prefetch_related("vente__lignes")
    serializer_class = FactureSerializer
    permission_classes = [IsAuthenticated]
