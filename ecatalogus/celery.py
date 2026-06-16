import os
from celery import Celery

from ecatalogus.env_loader import load_runtime_env

# Set the default Django settings module for the 'celery' program.
settings_module = load_runtime_env()
os.environ.setdefault('DJANGO_SETTINGS_MODULE', settings_module)

app = Celery('ecatalogus')

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Load task modules from all registered Django apps.
app.autodiscover_tasks()


@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')