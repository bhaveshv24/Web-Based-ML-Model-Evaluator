from django.contrib.auth import get_user_model
from evaluations.serializers import EvaluationSerializer
from rest_framework import serializers

from .models import Workspace, WorkspaceMembership

User = get_user_model()


class WorkspaceSerializer(serializers.ModelSerializer):
    member_count = serializers.IntegerField(source="members.count", read_only=True)

    class Meta:
        model = Workspace
        fields = ("id", "name", "member_count", "created_at")
        read_only_fields = ("id", "member_count", "created_at")


class WorkspaceMemberSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def validate_email(self, value):
        try:
            return User.objects.get(email=value.lower(), is_active=True)
        except User.DoesNotExist as exc:
            raise serializers.ValidationError("Active user not found.") from exc

    def create(self, validated_data):
        membership, created = WorkspaceMembership.objects.get_or_create(
            workspace=self.context["workspace"], user=validated_data["email"]
        )
        if not created:
            raise serializers.ValidationError({"email": ["User is already a workspace member."]})
        return membership

    def to_representation(self, instance):
        return {
            "id": str(instance.user_id),
            "email": instance.user.email,
            "joined_at": instance.joined_at,
        }


class WorkspaceEvaluationSerializer(EvaluationSerializer):
    owner_email = serializers.EmailField(source="owner.email", read_only=True)

    class Meta(EvaluationSerializer.Meta):
        fields = EvaluationSerializer.Meta.fields + ("owner_email",)
