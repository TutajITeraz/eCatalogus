from django.apps import AppConfig


class IndexerappConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'indexerapp'

    def ready(self):
        import indexerapp.signals  # Import signals to register them