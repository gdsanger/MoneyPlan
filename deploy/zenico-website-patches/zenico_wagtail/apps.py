from django.apps import AppConfig


class ZenicoWagtailConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'zenico_wagtail'
    verbose_name = 'Zenico Wagtail patches'

    def ready(self):
        from . import signals  # noqa: F401
