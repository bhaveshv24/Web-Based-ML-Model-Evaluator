from rest_framework import serializers

from .models import Evaluation


class EvaluationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Evaluation
        fields = (
            "id",
            "workspace",
            "task_type",
            "status",
            "metrics_json",
            "error_message",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields
