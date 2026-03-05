# ETL Plan — Faza 0: Multi-instancja i refactoring

## TL;DR

Trzy etapy poprzedzające właściwą implementację ETL:
1. Uruchom obecną instancję LiturgicaPoloniae z danymi (weryfikacja działania przed jakimikolwiek zmianami)
2. Refactoring nazw: `ritus_indexer/` → `ecatalogus/`, `indexerapp/` → `catalogue/`, nazwy baz bez prefiksu `ritus_`
3. Konfiguracja multi-instancja: eCatalogus_main (master, port 8000) + LiturgicaPoloniae (slave, port 8080)

---

## Krok 0 — Uruchomienie obecnej instancji LiturgicaPoloniae

Cel: zweryfikować że dane z SQL działają zanim cokolwiek zmienimy.

**0.1 Utwórz usera i bazę MariaDB (obecna nazwa `ritus`):**

```bash
sudo mariadb -e "CREATE USER IF NOT EXISTS 'ecatalogus_user'@'127.0.0.1' IDENTIFIED BY 'SoftCatEarZ1563!';"
sudo mariadb -e "CREATE DATABASE IF NOT EXISTS ritus CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
sudo mariadb -e "GRANT ALL PRIVILEGES ON ritus.* TO 'ecatalogus_user'@'127.0.0.1';"
sudo mariadb -e "FLUSH PRIVILEGES;"
```

**0.2 Importuj dane:**

```bash
mariadb -u ecatalogus_user -p'SoftCatEarZ1563!' ritus < backup/ispan_mpl.sql
```

**0.3 Fake initial migration (schemat już istnieje z SQL):**

```bash
source .venv/bin/activate
python manage.py migrate --fake-initial
```

**0.4 Uruchom serwer i zweryfikuj:**

```bash
python manage.py runserver 127.0.0.1:8080
# open http://127.0.0.1:8080 and verify manuscripts list and admin
```

**Weryfikacja:** lista manuskryptów widoczna, admin działa, brak błędów 500.

## Krok 1 — Refactoring nazw

Cel: usunąć mylące nazwy `ritus_indexer` i `indexerapp`, ujednolicić pod markę eCatalogus.

### Mapa zmian

| Stara nazwa | Nowa nazwa | Uwagi |
|---|---|---|
| katalog `ritus_indexer/` | `ecatalogus/` | Django project package (settings, urls, wsgi, asgi) |
| katalog `indexerapp/` | `catalogue/` | Django app |
| string `'ritus_indexer'` w plikach | `'ecatalogus'` | settings module, wsgi, asgi |
| string `'indexerapp'` w plikach | `'catalogue'` | INSTALLED_APPS, app_label, migracje |
| baza danych `ritus` | `ecatalogus_liturgica` | tylko w settings |

### Zmiana katalogów przez `git mv`

```bash
git mv ritus_indexer ecatalogus
git mv indexerapp catalogue
```

### Zmiany zawartości plików (po git mv)

**`manage.py`:**
- `'ritus_indexer.settings'` → `'ecatalogus.settings'`

**`ecatalogus/wsgi.py`** (był `ritus_indexer/wsgi.py`):
- `'ritus_indexer.settings'` → `'ecatalogus.settings'`

**`ecatalogus/asgi.py`** (był `ritus_indexer/asgi.py`):
- `'ritus_indexer.settings'` → `'ecatalogus.settings'`

**`ecatalogus/settings.py`** (był `ritus_indexer/settings.py`):
- `'indexerapp'` → `'catalogue'` w `INSTALLED_APPS`
- `BASE_DIR / "indexerapp/static"` → `BASE_DIR / "catalogue/static"` w `STATICFILES_DIRS`
- `DATABASES['default']['NAME']` → `'ecatalogus_liturgica'`

**`ecatalogus/urls.py`** (był `ritus_indexer/urls.py`):
- `from indexerapp` → `from catalogue`

**`catalogue/apps.py`** (był `indexerapp/apps.py`):
- `name = 'indexerapp'` → `name = 'catalogue'`

**`catalogue/models.py`** i wszystkie pliki w `catalogue/`:
- Wszelkie `app_label = 'indexerapp'` → `app_label = 'catalogue'`

**`passenger_wsgi.py`:**
- `"ritus_indexer.settings"` → `"ecatalogus.settings"`

### Zmiana nazwy bazy

`RENAME DATABASE` nie istnieje w MariaDB — tworzymy nową i importujemy ponownie:

```bash
sudo mariadb -e "CREATE DATABASE ecatalogus_liturgica CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
sudo mariadb -e "GRANT ALL PRIVILEGES ON ecatalogus_liturgica.* TO 'ecatalogus_user'@'127.0.0.1';"
mariadb -u ecatalogus_user -p'SoftCatEarZ1563!' ecatalogus_liturgica < backup/ispan_mpl.sql
```

Stara baza `ritus` pozostaje jako backup do momentu pełnej weryfikacji.

**Weryfikacja po Kroku 1:**

```bash
python manage.py check
python manage.py migrate --fake-initial
python manage.py runserver 127.0.0.1:8080
# http://127.0.0.1:8080 should work identically as before refactoring
```

## Krok 2 — Multi-instancja

Cel: uruchomić dwie niezależne instancje z jednego repo na różnych portach.

### 2.1 Stwórz `ecatalogus/settings_base.py`

Skopiuj całą obecną zawartość `ecatalogus/settings.py` do `settings_base.py`, usuwając z niej:
- `SECRET_KEY`
- `DEBUG`
- `ALLOWED_HOSTS`
- `DATABASES`

### 2.2 Stwórz `ecatalogus/settings_liturgica.py` (slave, port 8080)

```python
from .settings_base import *

SECRET_KEY = '<current key from settings.py>'
DEBUG = True
ALLOWED_HOSTS = ['localhost', '127.0.0.1']

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': 'ecatalogus_liturgica',
        'USER': 'ecatalogus_user',
        'PASSWORD': 'SoftCatEarZ1563!',
        'HOST': '127.0.0.1',
    }
}

ETL_ROLE = 'slave'
ETL_MASTER_URL = 'http://127.0.0.1:8000'
ETL_API_TOKEN = 'liturgica-token-change-me'
```

### 2.3 Stwórz `ecatalogus/settings_main.py` (master eCatalogus_main, port 8000)

```python
from .settings_base import *

SECRET_KEY = 'ecatalogus-main-secret-key-change-me'
DEBUG = True
ALLOWED_HOSTS = ['localhost', '127.0.0.1']

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': 'ecatalogus_main',
        'USER': 'ecatalogus_user',
        'PASSWORD': 'SoftCatEarZ1563!',
        'HOST': '127.0.0.1',
    }
}

ETL_ROLE = 'master'
ETL_MASTER_URL = None
ETL_SLAVE_URLS = ['http://127.0.0.1:8080']
ETL_API_TOKEN = 'ecatalogus-main-token-change-me'

# Overlay: instance-specific static files take precedence over shared base
STATICFILES_DIRS = [
    BASE_DIR / "static_ecatalogus_main",  # overlay (create only when needed)
    BASE_DIR / "catalogue/static",         # shared base
]
```

### 2.4 Zaktualizuj `ecatalogus/settings.py` jako alias

```python
# Default settings — alias for LiturgicaPoloniae instance
# Kept for backward compatibility with passenger_wsgi.py and legacy scripts
from .settings_liturgica import *
```

### 2.5 Utwórz bazę dla eCatalogus_main

```bash
sudo mariadb -e "CREATE DATABASE ecatalogus_main CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
sudo mariadb -e "GRANT ALL PRIVILEGES ON ecatalogus_main.* TO 'ecatalogus_user'@'127.0.0.1';"
```

### 2.6 Zaaplikuj migracje

```bash
# LiturgicaPoloniae — schema already exists from SQL dump
DJANGO_SETTINGS_MODULE=ecatalogus.settings_liturgica python manage.py migrate --fake-initial

# eCatalogus_main — empty database, normal migrate
DJANGO_SETTINGS_MODULE=ecatalogus.settings_main python manage.py migrate
```

### 2.7 Stwórz skrypty startowe

`run_liturgica.sh`:

```bash
#!/bin/bash
export DJANGO_SETTINGS_MODULE=ecatalogus.settings_liturgica
source .venv/bin/activate
python manage.py runserver 127.0.0.1:8080
```

`run_ecatalogus_main.sh`:

```bash
#!/bin/bash
export DJANGO_SETTINGS_MODULE=ecatalogus.settings_main
source .venv/bin/activate
python manage.py runserver 127.0.0.1:8000
```

```bash
chmod +x run_liturgica.sh run_ecatalogus_main.sh
```

**Weryfikacja:**

```bash
# Terminal 1
./run_liturgica.sh
# http://127.0.0.1:8080 — SQL data visible, admin works

# Terminal 2
./run_ecatalogus_main.sh
# http://127.0.0.1:8000 — empty database, Django admin works
```

