import subprocess

while True:
    subprocess.run('export DUBO_API_KEY="pk.bb63cda35d47463fb858192bee22510f"; python manage.py runserver 0.0.0.0:8080')
