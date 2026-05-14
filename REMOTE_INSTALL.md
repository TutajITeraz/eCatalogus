# Remote install and update guide (EN)

This repository includes bash-based tools to install and update Django instances served by Gunicorn + Nginx on Ubuntu (DirectAdmin-managed domains).

Goal
 - Provide repeatable, git-based installation and update scripts.
 - Keep instance-specific settings and files preserved across updates.
 - Offer an interactive installer (uses `whiptail` if available, falls back to stdin prompts).

What is included
 - `scripts/install_instance.sh` — installer that validates config early, clones or updates the repo, creates a virtualenv, installs dependencies, downloads frontend libraries, runs `check`, `migrate`, `collectstatic`, refreshes symlinks/permissions, renders managed per-instance settings files, and writes a per-instance config under `scripts/config/`.
 - `scripts/deploy_update.sh` — update script that validates config, preserves local files listed in the config, refuses unexpected dirty working trees, renders managed per-instance settings files, downloads frontend libraries, runs `check`, `makemigrations`, `migrate`, `collectstatic`, refreshes symlinks/permissions, installs or renders the DirectAdmin CUSTOM3 snippet, and restarts the service when possible.
 - `scripts/config/example.env` — example environment file showing configurable values (domain, repo URL, branch, paths, preserve list, socket/port, etc.).
 - `deploy/gunicorn.service.template` — systemd service template with placeholders. The installer writes a rendered copy into `deploy/` for review; installing the unit on the server requires root.
 - `deploy/gunicorn.service.template` — systemd service template with placeholders. The installer writes a rendered copy into `deploy/` for review; installing the unit on the server requires root (or use `--install-unit` when running the installer with sudo/root).

Design decisions
 - Scripts always use `git` to obtain code. On existing checkouts they preserve configured files before reset and abort if they detect unexpected local changes.
 - Local instance-specific files that are truly local-only can be preserved by copying them out before `git reset` and restoring them afterwards. Configure the list via `PRESERVE_FILES` in the env file. Do not preserve managed files such as `ecatalogus/settings.py`, `ecatalogus/settings_mpl.py`, `ecatalogus/settings_ecatalogus.py`, or repo-owned overlay static files.
 - By default the service binds to a Unix socket (recommended for Nginx). TCP mode is supported; the installer checks port availability when TCP is selected.
 - The scripts now run `makemigrations indexerapp --noinput` before `migrate`, because this deployment workflow intentionally generates production migrations per environment.
 - If you pass a config file to `install_instance.sh`, it is used as-is unless you explicitly request `--edit-config`.
 - The scripts are English-only and log each run to the instance `logs/` directory.
 - The scripts will generate the systemd unit into `deploy/` but will only install it to `/etc/systemd/system/` if you explicitly allow it and run the script with root (or use `sudo`).

Prerequisites (server)
 - Domain created in DirectAdmin (domain directory structure exists).
 - `git` and a system Python matching the target environment installed.
 - `whiptail` recommended for nicer interactive prompts (optional).
 - `gunicorn` will be installed into the instance virtualenv and `systemd` will be used to run the service (copy the generated unit to `/etc/systemd/system/` as root).

How to use
 - Prepare a per-instance env file in `scripts/config/<domain>.env` (copy `scripts/config/example.env` and edit values).
 - Run install using a prepared config file:
	 - `./scripts/install_instance.sh scripts/config/<domain>.env`
 - Re-open config editing explicitly when needed:
	 - `./scripts/install_instance.sh scripts/config/<domain>.env --edit-config`
 - Or run without an explicit file to walk through values and save a config:
	 - `./scripts/install_instance.sh`
 - Use `--dry-run` to preview actions without making changes:
 	 - `./scripts/install_instance.sh scripts/config/<domain>.env --dry-run`
 - Use `--non-interactive` in automation when the config file is complete:
	 - `./scripts/install_instance.sh scripts/config/<domain>.env --action full --non-interactive`
 - If the checkout contains local script changes that you intentionally want to discard and replace from git:
	 - `./scripts/install_instance.sh scripts/config/<domain>.env --action full --non-interactive --force-reset`
 - To install and enable the generated systemd unit in one step (requires root or sudo):
 	 - `sudo ./scripts/install_instance.sh scripts/config/<domain>.env --install-unit`
 - Update (on the server, as the deploy user):
	 - `./scripts/deploy_update.sh scripts/config/<domain>.env`

Notes about systemd and privileges
 - Creating and enabling the systemd unit requires root. The installer will render `deploy/{SERVICE_SHORTNAME}.service` inside the repo for review.
 - To install the unit, copy the rendered file to `/etc/systemd/system/`, then run:
	 - `sudo systemctl daemon-reload && sudo systemctl enable --now {SERVICE_SHORTNAME}`

Secrets and runtime `.env`
 - The installer and deploy scripts will source a per-instance secrets file at `APPDIR/.env` (for example `/home/ispan/domains/example.com/ecatalogus/.env`) if present. This file should NOT be committed to git and should contain runtime secrets such as `SECRET_KEY`, DB overrides, and tokens expected by your Django settings.
 - The installer can offer to create this `.env` interactively and will set secure permissions (owner `DEPLOY_USER`, mode `600`).
 - Keep non-secret configuration in `scripts/config/<domain>.env` (this file is stored in the repo). The installer writes back the effective configuration for later updates.

Where to put the runtime `.env`
- Create the runtime secrets file at `APPDIR/.env` (for example `/home/ispan/domains/example.com/ecatalogus/.env`).
- The installer will source this file automatically before running Django `manage.py` commands. If it is missing the installer can create it interactively.
- Ensure the file is owned by the deploy user and readable only by that user:

```bash
chown ispan:ispan /home/ispan/domains/example.com/ecatalogus/.env
chmod 600 /home/ispan/domains/example.com/ecatalogus/.env
```

Socket vs TCP
 - Unix sockets are preferred for Nginx proxying and avoid exposing ports. The default template uses a socket under the domain `public_html` directory.
 - If you need TCP, set `USE_TCP=1` and provide a free `PORT` in the env file. The installer will try to detect if the port is free and will abort if it is in use.

Preserving local files
 - Edit `PRESERVE_FILES` in the env file (comma-separated list) to list files relative to the app directory that must not be overwritten by `git reset` (for example local `settings.py` or `config.js`). If the checkout contains unexpected local changes outside that list, the scripts abort instead of resetting over them unless you explicitly pass `--force-reset`.

Logging
 - Each run writes a timestamped log into the instance `logs/` directory (configured by `LOG_DIR` in the env file).

Notes
 - The installer validates critical config values before it touches sockets, git, or the filesystem, so an empty `APPDIR` or `REPO_URL` fails immediately instead of falling through.
 - The installer and deploy script render managed instance settings files on the server based on `DJANGO_SETTINGS_MODULE`. This keeps multi-instance overlays (`static_mpl/`, `static_ecatalogus/`) active even when instance settings files are gitignored.
 - For multi-instance setups, keep media separated per instance. A recommended pattern is `APPDIR/media_instances/<instance_name>/` and setting `MEDIA_ROOT` accordingly in each managed settings file.
 - The install and deploy scripts now also render per-instance cookie names and per-instance `MEDIA_ROOT` defaults for the managed `settings_mpl` and `settings_ecatalogus` modules.
 - When upgrading an older single-instance install, the scripts can migrate files from legacy `APPDIR/media` into the new per-instance media directory if the new target is still empty.
 - The deploy script restarts the service when it can. If sudo is unavailable, it prints a warning so you can restart the service manually.

Adding a new instance
 - 1. Locally, run the instance creator to prepare the instance files:
	 - `python scripts/instance_creator.py <instance_slug>`
	 - This generates `scripts/config/<instance_slug>.env`, `ecatalogus/settings_<instance_slug>.py`, and other necessary files. The creator will prompt for instance type (e.g., ecatalogus or mpl), media directory, and other settings.
 - 2. Commit the generated files to the repository.
 - 3. Create the domain in DirectAdmin so the domain directories already exist.
 - 4. On the server, clone or update the repository in the app directory (e.g., `/home/ispan/domains/example.com/ecatalogus`):
	 - If not cloned: `git clone https://github.com/TutajITeraz/eCatalogus.git .`
	 - If already cloned: `git pull https://github.com/TutajITeraz/eCatalogus.git main`
 - 5. Run the installer with the generated config:
	 - `./scripts/install_instance.sh scripts/config/<instance_slug>.env --action full --non-interactive`
 - 6. To install and enable the generated systemd unit immediately:
	 - `sudo ./scripts/install_instance.sh scripts/config/<instance_slug>.env --action full --non-interactive --install-unit`
 - 7. Verify the selected overlay before opening the site:
	 - `source .venv/bin/activate`
	 - `export DJANGO_SETTINGS_MODULE=<value from config>`
	 - `python manage.py findstatic js/config.js img/logo_flat.svg --verbosity 2`
 - 8. Confirm that `public_html/static` points to `static_assets` and that collected files were refreshed:
	 - `readlink "$PUBLIC_HTML/static"`
	 - `ls -l "$APPDIR/static_assets/img/logo_flat.svg"`
 - 9. For later updates use:
	 - `./scripts/deploy_update.sh scripts/config/<instance_slug>.env`

Upgrading an older single-instance install
 - If the old install served media directly from `APPDIR/media`, run `./scripts/deploy_update.sh scripts/config/<domain>.env` first.
 - The script will refresh managed settings, point symlinks at the per-instance media directory, and render an updated DirectAdmin CUSTOM3 snippet in `deploy/`.
 - If your server already has an old CUSTOM3 snippet with `alias .../media/`, update that snippet once so Nginx points to the new per-instance media directory, then run the DirectAdmin config rewrite step.


