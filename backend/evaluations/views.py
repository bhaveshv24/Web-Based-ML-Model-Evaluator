"""Private, paginated and filterable evaluation history."""

from django.utils.dateparse import parse_datetime
from rest_framework import generics
from rest_framework.exceptions import ValidationError

from .models import Evaluation
from .serializers import EvaluationSerializer


class EvaluationListView(generics.ListAPIView):
    serializer_class = EvaluationSerializer

    def get_queryset(self):
        queryset = Evaluation.objects.filter(owner=self.request.user)
        status_value = self.request.query_params.get("status")
        task_type = self.request.query_params.get("task_type")

        if status_value:
            if status_value not in Evaluation.Status.values:
                raise ValidationError({"status": ["Unknown evaluation status."]})
            queryset = queryset.filter(status=status_value)
        if task_type:
            if task_type not in Evaluation.TaskType.values:
                raise ValidationError({"task_type": ["Unknown task type."]})
            queryset = queryset.filter(task_type=task_type)

        for parameter, lookup in (("from", "created_at__gte"), ("to", "created_at__lte")):
            raw_value = self.request.query_params.get(parameter)
            if raw_value:
                value = parse_datetime(raw_value)
                if value is None:
                    raise ValidationError({parameter: ["Use an ISO-8601 date-time."]})
                queryset = queryset.filter(**{lookup: value})
        return queryset


class EvaluationDetailView(generics.RetrieveDestroyAPIView):
    serializer_class = EvaluationSerializer
    lookup_field = "id"

    def get_queryset(self):
        return Evaluation.objects.filter(owner=self.request.user)
