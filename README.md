# About the Liturgica Poloniae project

This repository contains the latest version of the online platform for manuscript analysis, which is being developed as part of the Liturgica Poloniae project for the Institute of Art of the Polish Academy of Sciences (Instytut Sztuki Polskiej Akademii Nauk).
The base for the development is the code of the platform, which was previously developed as part of the eCLLA+ project ( https://github.com/TutajITeraz/eCLLA_Plus/ )

The project aims to create an interactive catalog of Latin liturgical manuscripts available via the website. This catalog will contain a general description of the manuscript, its bibliography, and will also enable the introduction of information about its contents regarding many different disciplines (rites, formulas, liturgy, codicology, musicology, decoration, paleography and others).

## Sample screanshoots:

### Listing and filtering Manuscripts
![Listing and filtering Manuscripts](README_assets/list_filtering.png?raw=true "Listing and filtering Manuscripts")
### Manuscript details and IIIF browser
![Manuscript details](README_assets/ms_details.png?raw=true "Manuscript details")
### Compare content
![Compare content](README_assets/compare_content.png?raw=true "Compare content")
### Graph of formulas order in the Manuscripts
![Graph of formulas order in the Manuscripts](README_assets/order_graph.png?raw=true "Graph of formulas order in the Manuscripts")
### Calculate similarity of the Manuscripts
![Calculate similarity of the Manuscripts](README_assets/similarity.png?raw=true "Calculate similarity of the Manuscripts")

### Other Features:
- Integratet IIIF viewer
- Integrated AI Assistant (via DUBO)
- Zotero Bibliography integration
- .csv data import with checks and foreign keys lookup
- XML TEI export (basic data only)
- Export to print

# Installing database engine

## For manjaro linux:
```
    sudo pacman -Syu
    sudo pacman -S mariadb
```
## For ubuntu linux:
```
    sudo apt update
    sudo apt install mariadb-server
    sudo mysql_secure_installation
```
## Configuring database engine:
```
    sudo mariadb-install-db --user=mysql --basedir=/usr --datadir=/var/lib/mysql
    sudo systemctl enable mariadb --now

    sudo mysql -u root
        CREATE DATABASE ritus;
        CREATE USER ritus_user@localhost IDENTIFIED BY 'SoftCatEarZ1563!';


        GRANT ALL PRIVILEGES ON ritus.* TO ritus_user@localhost ;

        FLUSH PRIVILEGES;
        exit
```


# Configuration:
Edit the ritus_indexer/settings.py:

Add your host to the variables:
```
ALLOWED_HOSTS
CSRF_TRUSTED_ORIGINS
CORS_ALLOWED_ORIGINS
```
Edit username and password for the database:
```
DATABASES
```
## example DATABASES config:
```
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
		'CONN_MAX_AGE': 0,
        'NAME': 'ritus',
        'USER': 'ritus_user',
        'PASSWORD': 'SoftCatEarZ1563!',
        'HOST': '127.0.0.1',
    }
}
```


# Installation

## Following commands must be executed in the project directory!
```

#Check pip version:
    pip --version
#If pip is not installed, install it:
#Manjaro linux command:
    pacman -Syu python-pip
#Ubuntu linux command:
    sudo apt install Python3-pip 

#Install pkg-config (Ubuntu):
    sudo apt install pkg-config
#Install pkg-config (Manjaro):
    sudo pamac install pkg-config


python3 -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt

#For a fresh install (no database migration) execute the following operations:
rm indexerapp/migrations/*
python manage.py makemigrations indexerapp
python manage.py migrate
python manage.py createsuperuser #This creates first user that you can use for log in

#For importing existing .sql file (moving database), change filename/path if needed and execute:
sudo mysql -u root -h localhost -p ritus < ~/Downloads/reboldho_indexer.sql


#Setup static files (may be served using nginex apache or other server):
python manage.py collectstatic

```

## Run server:

```
python manage.py runserver 0.0.0.0:8080
```



### Every time you want to run the project, you have to activate the environment first:
	source .venv/bin/activate
### And then run the mysql server
    sudo systemctl enable mariadb --now
### And finaly run the indexer django server:
	python manage.py runserver 0.0.0.0:8080


# Installation on a production server

Copy all files to the ritus directory

## Setup python WSGI app:

```
Python version: 3.11
Application root: domains/YOUR-DOMMAIN-NAME.com/ritus
Application URL: YOUR-DOMMAIN-NAME.com 
Application startup file: passenger_wsgi.py
Application Entry point: application
```

## Change content of the passenger_wsgi.py (it can be overwritten by the wsgi setup):

```
import os
import sys

# full path to the catalogue that includes manage.py
PROJECT_DIR = "/home2/YOUR-HOSTING-USER/domains/YOUR-DOMMAIN-NAME.com/ritus"

# insert to sys.path
sys.path.insert(0, PROJECT_DIR)

# ritus_indexer - name of a folder that includes settings.py
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ritus_indexer.settings")

from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
```


### In the settings.py set:

DEBUG = False

### and delete:

STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

## Create symlinks for static and media directories:

```
cd /home2//YOUR-HOSTING-USER/domains/YOUR-DOMMAIN-NAME.com/public_html
ln -s ../ritus/media media
ln -s ../ritus/static_assets static
```

## Run:

source /home2/YOUR-HOSTING-USER/virtualenv/domains/YOUR-DOMMAIN-NAME.com/ritus/3.11/bin/activate && cd /home2/YOUR-HOSTING-USER/domains/YOUR-DOMMAIN-NAME.com/ritus
pip install -r requirements.txt
python manage.py makemigrations
python manage.py migrate
python manage.py collectstatic
