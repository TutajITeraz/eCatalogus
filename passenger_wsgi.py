import os
import sys

# Limit OpenBLAS to use 2 threads
os.environ["OPENBLAS_NUM_THREADS"] = "2"


# full path to directory that contains manage.py
PROJECT_DIR = "/home2/reboldho/domains/monumenta-poloniae-liturgica.ispan.pl/ritus"

# add to sys.path
sys.path.insert(0, PROJECT_DIR)

# name of the folder with settings.py (replace XXX with the real name, e.g. "ritus" or "monumenta")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ritus_indexer.settings")

from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()

