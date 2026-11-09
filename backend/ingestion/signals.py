"""Remove upload bytes when their database records are deleted."""

from django.db.models.signals import post_delete
from django.dispatch import receiver

from .models import Dataset, ModelArtifact


@receiver(post_delete, sender=ModelArtifact)
@receiver(post_delete, sender=Dataset)
def delete_uploaded_file(sender, instance, **kwargs):
    if instance.file:
        instance.file.delete(save=False)
