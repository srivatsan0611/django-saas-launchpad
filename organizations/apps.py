from django.apps import AppConfig


class OrganizationsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "organizations"

    def ready(self):
        """
        Import signal handlers when the app is ready.
        This ensures signals are registered before the app starts.
        """
        import organizations.signals
