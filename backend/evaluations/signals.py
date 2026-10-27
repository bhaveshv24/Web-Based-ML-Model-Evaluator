"""Remove stored files whenever owned database records are deleted."""

from django.db.models.signals import post_delete
from django.dispatch import receiver

from .models import EvaluationArtifact, Report


@receiver(post_delete, sender=EvaluationArtifact)
@receiver(post_delete, sender=Report)
def delete_stored_file(sender, instance, **kwargs):
    if instance.file:
        instance.file.delete(save=False)
