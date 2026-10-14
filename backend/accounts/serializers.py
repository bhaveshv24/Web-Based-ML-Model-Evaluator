"""Authentication request and response schemas."""

from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from .models import User


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8, trim_whitespace=False)

    class Meta:
        model = User
        fields = ("id", "email", "password", "role")
        read_only_fields = ("id", "role")

    def validate_email(self, value):
        normalized = value.lower()
        if User.objects.filter(email__iexact=normalized).exists():
            raise serializers.ValidationError("An account with this email exists.")
        return normalized

    def validate_password(self, value):
        if not any(character.isalpha() for character in value) or not any(
            character.isdigit() for character in value
        ):
            raise serializers.ValidationError("Password must contain letters and digits.")
        validate_password(value)
        return value

    def create(self, validated_data):
        return User.objects.create_user(**validated_data)


class RoleTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token["role"] = user.role
        return token

    def validate(self, attrs):
        data = super().validate(attrs)
        data["role"] = self.user.role
        data["user_id"] = str(self.user.id)
        return data


class LogoutSerializer(serializers.Serializer):
    refresh = serializers.CharField()
