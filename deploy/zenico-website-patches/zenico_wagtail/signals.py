from django.db.models.signals import pre_save
from django.dispatch import receiver
from wagtail.models import Site

from .utils import normalize_site_hostname


@receiver(pre_save, sender=Site)
def normalize_wagtail_site_hostname(sender, instance, **kwargs):
    cleaned = normalize_site_hostname(instance.hostname)
    if cleaned != instance.hostname:
        instance.hostname = cleaned
