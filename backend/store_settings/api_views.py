from rest_framework.generics import RetrieveUpdateAPIView

from .models import ConfigurationMagasin
from .serializers import ConfigurationMagasinSerializer
from .permissions import ConfigurationMagasinPermission


class ConfigurationMagasinAPIView(RetrieveUpdateAPIView):
    serializer_class = ConfigurationMagasinSerializer
    permission_classes = [ConfigurationMagasinPermission]

    def get_object(self):
        configuration, created = ConfigurationMagasin.objects.get_or_create(
            pk=1
        )
        return configuration