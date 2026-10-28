from rest_framework import serializers

from .models import Evaluation


class EvaluationSerializer(serializers.ModelSerializer):
    model_id = serializers.UUIDField(source="model_artifact_id", read_only=True)
    dataset_id = serializers.UUIDField(read_only=True)
    duration_seconds = serializers.FloatField(read_only=True)

    class Meta:
        model = Evaluation
        fields = (
            "id",
            "workspace",
            "task_type",
            "task_type_overridden",
            "status",
            "metrics_json",
            "error_code",
            "error_message",
            "model_id",
            "dataset_id",
            "model_sha256",
            "dataset_sha256",
            "target_column",
            "sandbox_image",
            "started_at",
            "finished_at",
            "duration_seconds",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class EvaluationDetailSerializer(EvaluationSerializer):
    """API-09: detail additionally carries the stored chart data (FR-021, IT-EXE-07)."""

    class Meta(EvaluationSerializer.Meta):
        fields = EvaluationSerializer.Meta.fields + ("charts_json",)
        read_only_fields = fields


class EvaluationStatusSerializer(serializers.ModelSerializer):
    """API-16: lightweight polling payload (UI-03 polls every 2 s)."""

    duration_seconds = serializers.FloatField(read_only=True)

    class Meta:
        model = Evaluation
        fields = (
            "id",
            "status",
            "task_type",
            "error_code",
            "error_message",
            "started_at",
            "finished_at",
            "duration_seconds",
            "updated_at",
        )
        read_only_fields = fields


class EvaluationCreateSerializer(serializers.Serializer):
    """API-15 input: model_id, dataset_id, optional task_type override and workspace."""

    model_id = serializers.UUIDField()
    dataset_id = serializers.UUIDField()
    task_type = serializers.ChoiceField(
        choices=Evaluation.TaskType.choices, required=False, allow_null=True, allow_blank=True
    )
    workspace_id = serializers.UUIDField(required=False, allow_null=True)
