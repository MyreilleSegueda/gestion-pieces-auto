
from django.db.models import Q
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from accounts.role_permissions import ADMINISTRATOR_ROLE
from rest_framework import serializers

User = get_user_model()


class UtilisateurSerializer(serializers.ModelSerializer):
    roles = serializers.SlugRelatedField(
        many=True,
        slug_field="name",
        queryset=Group.objects.all(),
        source="groups",
        required=False,
    )
    mot_de_passe = serializers.CharField(
        write_only=True,
        required=False,
        allow_blank=False,
    )

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "first_name",
            "last_name",
            "email",
            "is_active",
            "roles",
            "mot_de_passe",
        ]
        read_only_fields = ["id"]

    def validate(self, attrs):
        request = self.context.get("request")
        if (
            self.instance is not None
            and request is not None
            and request.user.pk == self.instance.pk
            and attrs.get("is_active") is False
        ):
            raise serializers.ValidationError({
                "is_active": "Tu ne peux pas désactiver ton propre compte."
            })

        if self.instance is not None and self._is_administrator(self.instance):
            disabling = attrs.get("is_active") is False
            replacing_groups = "groups" in attrs
            remains_administrator = self.instance.is_staff or (
                replacing_groups
                and any(group.name == ADMINISTRATOR_ROLE for group in attrs["groups"])
            )
            removing_last_admin = replacing_groups and not remains_administrator
            if (disabling or removing_last_admin) and not self._has_other_administrator(
                self.instance
            ):
                raise serializers.ValidationError({
                    "roles": "Au moins un compte administrateur actif doit être conservé."
                })

        password = attrs.get("mot_de_passe")
        if self.instance is None and not password:
            raise serializers.ValidationError({
                "mot_de_passe": "Le mot de passe est obligatoire."
            })

        if password:
            user = self.instance or User(username=attrs.get("username", ""))
            try:
                validate_password(password, user)
            except DjangoValidationError as error:
                raise serializers.ValidationError({
                    "mot_de_passe": error.messages
                }) from error

        return attrs

    @staticmethod
    def _is_administrator(user):
        return user.is_staff or user.groups.filter(name=ADMINISTRATOR_ROLE).exists()

    @staticmethod
    def _has_other_administrator(user):
        return (
            User.objects.filter(is_active=True)
            .filter(Q(is_staff=True) | Q(groups__name=ADMINISTRATOR_ROLE))
            .exclude(pk=user.pk)
            .distinct()
            .exists()
        )

    def create(self, validated_data):
        password = validated_data.pop("mot_de_passe", None)
        groups = validated_data.pop("groups", [])
        user = User.objects.create_user(
            password=password,
            **validated_data,
        )
        user.groups.set(groups)
        return user

    def update(self, instance, validated_data):
        password = validated_data.pop("mot_de_passe", None)
        groups = validated_data.pop("groups", None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        if password:
            instance.set_password(password)

        instance.save()

        if groups is not None:
            instance.groups.set(groups)

        return instance


class RoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Group
        fields = ["id", "name"]
