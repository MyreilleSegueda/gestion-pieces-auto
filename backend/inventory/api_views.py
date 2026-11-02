
from uuid import UUID

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from django.db.models.deletion import ProtectedError
from rest_framework import viewsets
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import BasePermission, SAFE_METHODS
from rest_framework.response import Response
from rest_framework import status

from accounts.role_permissions import has_module_access
from .models import Categorie, PieceDetachee, MouvementStock
from .serializers import (
    CategorieSerializer,
    PieceDetacheeSerializer,
    MouvementStockSerializer,
)


class IsStockReaderOrManager(BasePermission):
    def has_permission(self, request, view):
        user = request.user
        return has_module_access(user, "stock", write=request.method not in SAFE_METHODS)


class CategorieViewSet(viewsets.ModelViewSet):
    queryset = Categorie.objects.all()
    serializer_class = CategorieSerializer
    permission_classes = [IsStockReaderOrManager]

    def destroy(self, request, *args, **kwargs):
        category = self.get_object()
        try:
            self.perform_destroy(category)
        except ProtectedError:
            return Response(
                {
                    "detail": (
                        "Impossible de supprimer cette catégorie : "
                        "des pièces y sont encore rattachées."
                    )
                },
                status=status.HTTP_409_CONFLICT,
            )
        return Response(status=status.HTTP_204_NO_CONTENT)


class PieceDetacheeViewSet(viewsets.ModelViewSet):
    queryset = PieceDetachee.objects.select_related("categorie").all()
    serializer_class = PieceDetacheeSerializer
    permission_classes = [IsStockReaderOrManager]
    http_method_names = ["get", "post", "put", "patch", "head", "options"]


class MouvementStockViewSet(viewsets.ModelViewSet):
    queryset = MouvementStock.objects.select_related("piece").all()
    serializer_class = MouvementStockSerializer
    permission_classes = [IsStockReaderOrManager]
    http_method_names = ["get", "post", "head", "options"]

    def create(self, request, *args, **kwargs):
        raw_key = request.headers.get("Idempotency-Key")
        try:
            idempotency_key = UUID(raw_key or "")
        except (ValueError, TypeError, AttributeError) as error:
            raise ValidationError({
                "idempotency_key": "L'en-tête Idempotency-Key doit contenir un UUID."
            }) from error

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        existing = MouvementStock.objects.filter(
            idempotency_key=idempotency_key
        ).first()

        if existing is not None:
            if self._same_payload(existing, serializer.validated_data):
                return Response(
                    self.get_serializer(existing).data,
                    status=status.HTTP_200_OK,
                )
            return Response(
                {"detail": "Cette clé a déjà été utilisée pour un autre mouvement."},
                status=status.HTTP_409_CONFLICT,
            )

        try:
            with transaction.atomic():
                serializer.save(
                    utilisateur=request.user,
                    idempotency_key=idempotency_key,
                )
        except IntegrityError:
            existing = MouvementStock.objects.filter(
                idempotency_key=idempotency_key
            ).first()
            if existing is None:
                raise
            if self._same_payload(existing, serializer.validated_data):
                return Response(
                    self.get_serializer(existing).data,
                    status=status.HTTP_200_OK,
                )
            return Response(
                {"detail": "Cette clé a déjà été utilisée pour un autre mouvement."},
                status=status.HTTP_409_CONFLICT,
            )
        except DjangoValidationError as error:
            raise ValidationError(error.messages) from error

        headers = self.get_success_headers(serializer.data)
        return Response(
            serializer.data,
            status=status.HTTP_201_CREATED,
            headers=headers,
        )

    def _same_payload(self, movement, validated_data):
        return movement.utilisateur_id == self.request.user.pk and all(
            getattr(movement, field) == value
            for field, value in validated_data.items()
        )

    def perform_create(self, serializer):
        try:
            serializer.save(utilisateur=self.request.user)
        except DjangoValidationError as error:
            raise ValidationError(error.messages) from error

    def get_queryset(self):
        queryset = super().get_queryset()

        piece_id = self.request.query_params.get("piece")
        type_mouvement = self.request.query_params.get("type")

        if piece_id:
            queryset = queryset.filter(piece_id=piece_id)

        if type_mouvement:
            queryset = queryset.filter(type_mouvement=type_mouvement)

        return queryset
