from __future__ import annotations

import argparse
import getpass
import os
import secrets
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
REGISTRY_PATH = REPO_ROOT / 'scripts' / 'config' / 'instance_registry.toml'
BASE_LOGO_PATH = REPO_ROOT / 'indexerapp' / 'static' / 'img' / 'logo_flat.svg'
BASE_ABOUT_PATH = REPO_ROOT / 'static_assets' / 'about.html'


def slugify(value: str) -> str:
    normalized = ''.join(ch.lower() if ch.isalnum() else '-' for ch in value.strip())
    parts = [part for part in normalized.split('-') if part]
    return '-'.join(parts)


def env_prefix_for(slug: str) -> str:
    return slug.upper().replace('-', '_')


def title_from_slug(slug: str) -> str:
    return slug.replace('-', ' ').replace('_', ' ').title()


def prompt_text(label: str, default: str, *, example: str | None = None, interactive: bool = True) -> str:
    if not interactive:
        return default
    suffix = f' [{default}]' if default else ''
    if example:
        suffix += f' (example: {example})'
    response = input(f'{label}{suffix}: ').strip()
    return response or default


def prompt_secret(label: str, default: str, *, interactive: bool = True) -> str:
    if not interactive:
        return default

    suffix = ' [saved value]' if default else ''
    response = getpass.getpass(f'{label}{suffix}: ')
    return response or default


def prompt_yes_no(label: str, *, default: bool, interactive: bool = True) -> bool:
    if not interactive:
        return default

    suffix = ' [Y/n]' if default else ' [y/N]'
    response = input(f'{label}{suffix}: ').strip().lower()
    if not response:
        return default
    if response in {'y', 'yes'}:
        return True
    if response in {'n', 'no'}:
        return False
    raise ValueError(f'Unsupported yes/no value: {response}')


def prompt_choice(label: str, options: list[tuple[str, str]], default_value: str, *, interactive: bool = True) -> str:
    if not interactive:
        return default_value

    print(label)
    for index, (_, value) in enumerate(options, start=1):
        marker = ' [default]' if value == default_value else ''
        print(f'  {index}. {value}{marker}')

    response = input('Choose option number or press Enter: ').strip()
    if not response:
        return default_value
    if response.isdigit():
        selected_index = int(response) - 1
        if 0 <= selected_index < len(options):
            return options[selected_index][1]
    values = {value for _, value in options}
    if response in values:
        return response
    raise ValueError(f'Unsupported choice: {response}')


def load_registry() -> tuple[dict, list[str]]:
    if REGISTRY_PATH.exists():
        payload = tomllib.loads(REGISTRY_PATH.read_text(encoding='utf-8'))
    else:
        payload = {'version': 1, 'instances': {}}
    return payload, sorted(payload.get('instances', {}).keys())


def parse_env_file(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}

    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding='utf-8').splitlines():
        line = raw_line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, value = line.split('=', 1)
        values[key.strip()] = value.strip()
    return values


def read_env_value(env_values: dict[str, str], slug: str, name: str) -> str:
    env_prefix = env_prefix_for(slug)
    for key in (f'{env_prefix}_{name}', name):
        value = env_values.get(key, '').strip()
        if value:
            return value
    return ''


def first_non_empty(*values: str) -> str:
    for value in values:
        if value:
            return value
    return ''


def load_existing_instance_defaults(slug: str) -> dict[str, str]:
    local_env_path = REPO_ROOT / f'.env.{slug}'
    install_env_path = REPO_ROOT / 'scripts' / 'config' / f'{slug}.env'
    local_env = parse_env_file(local_env_path)
    install_env = parse_env_file(install_env_path)

    fallback_env_paths = [
        REPO_ROOT / '.env.mpl',
        REPO_ROOT / '.env.ecatalogus',
    ]
    fallback_envs = [parse_env_file(path) for path in fallback_env_paths if path.exists()]
    fallback_envs.extend(
        parse_env_file(path)
        for path in sorted(REPO_ROOT.glob('.env.*'))
        if path.name not in {f'.env.{slug}', '.env.mpl', '.env.ecatalogus'}
    )

    def fallback_value(name: str) -> str:
        for env_values in fallback_envs:
            for candidate_slug in ('mpl', 'ecatalogus'):
                value = read_env_value(env_values, candidate_slug, name)
                if value:
                    return value
            generic_value = env_values.get(name, '').strip()
            if generic_value:
                return generic_value
        return ''

    local_database_name = read_env_value(local_env, slug, 'DATABASE_NAME')
    local_database_user = read_env_value(local_env, slug, 'DATABASE_USER')
    local_database_password = read_env_value(local_env, slug, 'DATABASE_PASSWORD')
    fallback_database_user = first_non_empty(fallback_value('DATABASE_USER'), 'ecatalogus_user')
    fallback_database_password = fallback_value('DATABASE_PASSWORD')

    database_name = first_non_empty(local_database_name, slug)
    if local_database_password:
        database_user = first_non_empty(local_database_user, fallback_database_user)
        database_password = local_database_password
    else:
        # Treat the first generated scaffold values as placeholders and fall back
        # to the working shared local MariaDB credentials when no password exists.
        database_user = first_non_empty(
            local_database_user if local_database_user and local_database_user != slug else '',
            fallback_database_user,
        )
        database_password = fallback_database_password

    database_host = first_non_empty(read_env_value(local_env, slug, 'DATABASE_HOST'), fallback_value('DATABASE_HOST'), '127.0.0.1')
    database_port = first_non_empty(read_env_value(local_env, slug, 'DATABASE_PORT'), fallback_value('DATABASE_PORT'), '3306')

    return {
        'deploy_user': install_env.get('DEPLOY_USER', '').strip(),
        'database_name': database_name,
        'database_user': database_user,
        'database_password': database_password,
        'database_host': database_host,
        'database_port': database_port,
        'admin_username': first_non_empty(local_env.get('DJANGO_SUPERUSER_USERNAME', '').strip(), 'admin'),
        'admin_email': first_non_empty(local_env.get('DJANGO_SUPERUSER_EMAIL', '').strip(), 'admin@example.com'),
        'admin_password': first_non_empty(local_env.get('DJANGO_SUPERUSER_PASSWORD', '').strip(), 'admin'),
        'debug': first_non_empty(read_env_value(local_env, slug, 'DEBUG'), local_env.get('DEBUG', '').strip(), '1'),
        'secret_key': first_non_empty(read_env_value(local_env, slug, 'SECRET_KEY'), local_env.get('SECRET_KEY', '').strip(), secrets.token_urlsafe(48)),
        'etl_api_token': first_non_empty(read_env_value(local_env, slug, 'ETL_API_TOKEN'), local_env.get('ETL_API_TOKEN', '').strip(), secrets.token_urlsafe(32)),
        'instance_secret_key': first_non_empty(local_env.get(f'{env_prefix_for(slug)}_SECRET_KEY', '').strip(), secrets.token_urlsafe(48)),
        'instance_etl_api_token': first_non_empty(local_env.get(f'{env_prefix_for(slug)}_ETL_API_TOKEN', '').strip(), secrets.token_urlsafe(32)),
    }


def dump_value(value):
    if isinstance(value, bool):
        return 'true' if value else 'false'
    if isinstance(value, int):
        return str(value)
    if isinstance(value, list):
        return '[' + ', '.join(dump_value(item) for item in value) + ']'
    escaped = str(value).replace('\\', '\\\\').replace('"', '\\"')
    return f'"{escaped}"'


def dump_registry(payload: dict) -> str:
    lines = [f"version = {payload.get('version', 1)}", '']
    instances = payload.get('instances', {})
    for slug in sorted(instances):
        lines.append(f'[instances.{slug}]')
        for key, value in instances[slug].items():
            lines.append(f'{key} = {dump_value(value)}')
        lines.append('')
    return '\n'.join(lines).rstrip() + '\n'


def build_settings_module(instance: dict) -> str:
    allowed_hosts = [instance['domain'], '127.0.0.1', 'localhost']
    csrf_origins = [
        f"https://{instance['domain']}",
        f"http://{instance['domain']}",
        'https://127.0.0.1',
        'http://127.0.0.1',
    ]
    cors_origins = [
        'http://localhost:3000',
        'http://localhost:8000',
        f"https://{instance['domain']}",
        f"http://{instance['domain']}",
    ]
    source_peers = instance['source_peers']

    return f'''"""Instance settings for {instance['site_name']}. Safe to commit; secrets live in .env.{instance['slug']}."""

from .settings_base import *
from .instance_settings import apply_instance_settings


apply_instance_settings(
    globals(),
    instance_slug="{instance['slug']}",
    defaults={{
        "site_name": "{instance['site_name']}",
        "domain": "{instance['domain']}",
        "overlay_dir": "static_{instance['slug']}",
        "database_name": "{instance['database_name']}",
        "database_user": "{instance['database_user']}",
        "project_id": {instance['project_id']},
        "foreign_id_name": "{instance['foreign_id_name']}",
        "role": "{instance['role']}",
        "peer_id": "{instance['peer_id']}",
        "canonical_master_id": "ecatalogus",
        "default_parent_peer": "{instance['default_parent_peer']}",
        "source_peers": {source_peers!r},
        "public_url": "{instance['public_url']}",
        "allowed_hosts": {allowed_hosts!r},
        "csrf_trusted_origins": {csrf_origins!r},
        "cors_allowed_origins": {cors_origins!r},
    }},
)
'''


def build_run_script(instance: dict) -> str:
    return f'''#!/bin/bash
set -euo pipefail

export DJANGO_SETTINGS_MODULE=ecatalogus.settings_{instance['slug']}

if [[ -f .env.{instance['slug']} ]]; then
  set -a
  source .env.{instance['slug']}
  set +a
fi

source .venv/bin/activate
python manage.py runserver 127.0.0.1:{instance['local_port']}
'''


def build_instance_env(instance: dict, env_defaults: dict[str, str]) -> str:
    env_prefix = env_prefix_for(instance['slug'])
    return f'''# Local-only instance env for {instance['site_name']}
# Generated by scripts/instance_creator.py. Do not commit.

DJANGO_SETTINGS_MODULE=ecatalogus.settings_{instance['slug']}
SECRET_KEY={env_defaults['secret_key']}
DEBUG={env_defaults['debug']}
DATABASE_NAME={env_defaults['database_name']}
DATABASE_USER={env_defaults['database_user']}
DATABASE_PASSWORD={env_defaults['database_password']}
DATABASE_HOST={env_defaults['database_host']}
DATABASE_PORT={env_defaults['database_port']}
MEDIA_ROOT={REPO_ROOT / 'media_instances' / instance['slug']}
ETL_API_TOKEN={env_defaults['etl_api_token']}
ETL_SELF_PEER_ID={instance['peer_id']}
ETL_DEFAULT_PARENT_PEER={instance['default_parent_peer']}
ETL_SOURCE_PEERS={','.join(instance['source_peers'])}
INSTANCE_PUBLIC_URL={instance['public_url']}
DJANGO_SUPERUSER_USERNAME={env_defaults['admin_username']}
DJANGO_SUPERUSER_EMAIL={env_defaults['admin_email']}
DJANGO_SUPERUSER_PASSWORD={env_defaults['admin_password']}
{env_prefix}_SECRET_KEY={env_defaults['instance_secret_key']}
{env_prefix}_ETL_API_TOKEN={env_defaults['instance_etl_api_token']}
'''


def build_install_env(instance: dict, deploy_user: str) -> str:
    domain = instance['domain']
    return f'''# Generated by scripts/instance_creator.py for {instance['site_name']}
DOMAIN={domain}
DEPLOY_USER={deploy_user}
REPO_URL=git@github.com:yourorg/ecatalogus.git
GIT_BRANCH=main
APPDIR=/home/${{DEPLOY_USER}}/domains/${{DOMAIN}}/ecatalogus
VENV_PATH=${{APPDIR}}/.venv
PYTHON_BIN=python3.11
SERVICE_SHORTNAME={instance['slug']}
SOCKET_PATH=/home/${{DEPLOY_USER}}/domains/${{DOMAIN}}/public_html/gunicorn.sock
USE_TCP=0
PORT=
TCP_BIND_HOST=127.0.0.1
PRESERVE_FILES=local_settings.py
STATIC_DIR=${{APPDIR}}/static_assets
MEDIA_DIR=${{APPDIR}}/media_instances/{instance['slug']}
PUBLIC_HTML=/home/${{DEPLOY_USER}}/domains/${{DOMAIN}}/public_html
LOG_DIR=${{APPDIR}}/logs
DJANGO_SETTINGS_MODULE=ecatalogus.settings_{instance['slug']}
'''


def build_js_config(instance: dict) -> str:
    source_project = 'true' if instance['role'] == 'master' else 'false'
    return f'''// Instance config — {instance['site_name']}
// Generated by scripts/instance_creator.py.

window.SITE_CONFIG = (function () {{
    const origin = window.location.origin;

    const productionRoots = {{
        'https://{instance['domain']}': 'https://{instance['domain']}',
        'http://{instance['domain']}': 'https://{instance['domain']}',
    }};

    return {{
        pageRoot: productionRoots[origin] || origin,
        projectId: {instance['project_id']},
        siteName: '{instance['site_name']}',
        foreign_id_name: '{instance['foreign_id_name']}',
        features: {{
            sourceProject: {source_project},
            sourceProjectFilter: {source_project},
        }},
        uiVisibility: {{
            menu: {{
                about: true,
                manuscripts: true,
                contentAnalysis: true,
                aiTools: true,
            }},
            manuscriptFilters: {{
                mainInfo: true,
                layout: true,
                binding: true,
                condition: true,
                content: true,
                musicology: true,
                decoration: true,
                bibliography: true,
            }},
            manuscriptSections: {{
                mainInfo: true,
                clla: true,
                codicology: true,
                watermarks: true,
                quires: true,
                layouts: true,
                scripts: true,
                mainHands: true,
                additionHands: true,
                musicNotation: true,
                binding: true,
                decoration: true,
                initials: true,
                miniatures: true,
                bordersOthers: true,
                condition: true,
                content: true,
                history: true,
                originsDating: true,
                provenanceHistory: true,
                bibliography: true,
            }},
        }},
    }};
}})();
'''


def sql_string(value: str) -> str:
    return value.replace("'", "''")


def sql_identifier(value: str) -> str:
    return value.replace('`', '``')


def setup_local_dev_database(instance: dict, env_defaults: dict[str, str], *, dry_run: bool) -> None:
    database_name = env_defaults['database_name']
    database_user = env_defaults['database_user']
    database_password = env_defaults['database_password']
    database_host = env_defaults['database_host'] or '127.0.0.1'

    if not database_user:
        raise ValueError('Local MariaDB setup requires a non-empty database user.')
    if not database_password:
        raise ValueError('Local MariaDB setup requires a non-empty database password.')

    sql_commands = [
        f"CREATE USER IF NOT EXISTS '{sql_string(database_user)}'@'{sql_string(database_host)}' IDENTIFIED BY '{sql_string(database_password)}';",
        f"CREATE DATABASE IF NOT EXISTS `{sql_identifier(database_name)}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;",
        f"GRANT ALL PRIVILEGES ON `{sql_identifier(database_name)}`.* TO '{sql_string(database_user)}'@'{sql_string(database_host)}';",
        'FLUSH PRIVILEGES;',
    ]

    for sql in sql_commands:
        if dry_run:
            masked_sql = sql.replace(sql_string(database_password), '***') if database_password else sql
            print(f'[dry-run] sudo mariadb -e "{masked_sql}"')
            continue
        try:
            subprocess.run(['sudo', 'mariadb', '-e', sql], check=True)
        except FileNotFoundError as exc:
            raise RuntimeError('Missing sudo or mariadb in PATH; cannot prepare local dev database automatically.') from exc
        except subprocess.CalledProcessError as exc:
            raise RuntimeError(f'Local MariaDB setup failed for instance {instance["slug"]}.') from exc


def run_local_bootstrap(instance: dict, local_env_path: Path, *, dry_run: bool) -> None:
    python_bin = REPO_ROOT / '.venv' / 'bin' / 'python'
    python_cmd = str(python_bin if python_bin.exists() else Path(sys.executable))

    env = os.environ.copy()
    env.update(parse_env_file(local_env_path))
    env['DJANGO_SETTINGS_MODULE'] = f"ecatalogus.settings_{instance['slug']}"

    migrate_cmd = [python_cmd, 'manage.py', 'migrate']
    if dry_run:
        print('[dry-run] ' + ' '.join(migrate_cmd))
        print('[dry-run] Django post_migrate will ensure the configured admin user from DJANGO_SUPERUSER_* values.')
        return

    try:
        subprocess.run(migrate_cmd, cwd=REPO_ROOT, env=env, check=True)
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(
            f'Local Django bootstrap failed for instance {instance["slug"]} during migrate/admin setup.'
        ) from exc


def collect_instance(interactive: bool, args) -> dict:
    existing_registry, existing_slugs = load_registry()
    existing_instances = existing_registry.get('instances', {})
    canonical_master_default = 'ecatalogus' if 'ecatalogus' in existing_slugs else ''

    raw_slug = args.slug or prompt_text('Instance slug', 'limbo', example='limbo', interactive=interactive)
    slug = slugify(raw_slug)
    if not slug:
        raise ValueError('Instance slug cannot be empty.')

    existing_entry = existing_instances.get(slug, {})
    existing_defaults = load_existing_instance_defaults(slug)

    if existing_entry and interactive:
        print(f'Updating existing instance: {slug}')

    site_name_default = existing_entry.get('site_name') or title_from_slug(slug)
    domain_default = existing_entry.get('domain') or f'{slug}.example.pl'
    deploy_user_default = existing_defaults['deploy_user'] or 'ispan'
    local_port_default = str(existing_entry.get('local_port') or '8081')

    site_name = args.site_name or prompt_text('Site name', site_name_default, example='Limbo', interactive=interactive)
    domain = args.domain or prompt_text('Primary domain', domain_default, example='limbo.example.pl', interactive=interactive)
    deploy_user = args.deploy_user or prompt_text('Deploy user', deploy_user_default, example='ispan', interactive=interactive)
    local_port = int(args.local_port or prompt_text('Local development port', local_port_default, example='8081', interactive=interactive))
    public_url_default = existing_entry.get('public_url') or f'https://{domain}'
    public_url = args.public_url or prompt_text('Public base URL', public_url_default, example=f'https://{domain}', interactive=interactive)
    role = args.role or prompt_choice(
        'Instance role',
        [('master', 'master'), ('slave', 'slave')],
        existing_entry.get('role', 'slave'),
        interactive=interactive,
    )

    default_parent_peer = ''
    source_peers = []
    if role == 'master':
        source_peers = existing_entry.get('source_peers') or [peer for peer in existing_slugs if peer != slug]
    else:
        parent_default = args.default_parent_peer or existing_entry.get('default_parent_peer') or canonical_master_default
        parent_choices = [(peer, peer) for peer in existing_slugs if peer != slug] or [('ecatalogus', 'ecatalogus')]
        default_parent_peer = prompt_choice(
            'Default ETL parent peer',
            parent_choices,
            parent_default or parent_choices[0][1],
            interactive=interactive,
        )
        source_peers = existing_entry.get('source_peers') or ([default_parent_peer] if default_parent_peer else [])

    foreign_id_name = args.foreign_id_name or prompt_text(
        'Foreign id label',
        existing_entry.get('foreign_id_name', 'foreign id'),
        example='MSPL no.',
        interactive=interactive,
    )
    project_id = int(args.project_id or prompt_text('Project id', str(existing_entry.get('project_id', '0')), example='2', interactive=interactive))

    database_name = args.database_name or prompt_text(
        'Local MariaDB database name',
        existing_defaults['database_name'],
        example=slug,
        interactive=interactive,
    )
    database_user = args.database_user or prompt_text(
        'Local MariaDB user',
        existing_defaults['database_user'],
        example='ecatalogus_user',
        interactive=interactive,
    )
    database_password = args.database_password or prompt_secret(
        'Local MariaDB password',
        existing_defaults['database_password'],
        interactive=interactive,
    )
    database_host = args.database_host or prompt_text(
        'Local MariaDB host for grants',
        existing_defaults['database_host'],
        example='127.0.0.1',
        interactive=interactive,
    )
    database_port = args.database_port or prompt_text(
        'Local MariaDB port',
        existing_defaults['database_port'],
        example='3306',
        interactive=interactive,
    )

    admin_username = args.admin_username or prompt_text(
        'Local admin username',
        existing_defaults['admin_username'],
        example='admin',
        interactive=interactive,
    )
    admin_email = args.admin_email or prompt_text(
        'Local admin email',
        existing_defaults['admin_email'],
        example='admin@example.com',
        interactive=interactive,
    )
    admin_password = args.admin_password or prompt_secret(
        'Local admin password',
        existing_defaults['admin_password'],
        interactive=interactive,
    )

    setup_dev_db = not args.skip_dev_db_setup
    if interactive and not args.skip_dev_db_setup:
        setup_dev_db = prompt_yes_no(
            'Create or update the local MariaDB user/database now',
            default=True,
            interactive=interactive,
        )

    bootstrap_local_django = not args.skip_local_bootstrap
    if interactive and not args.skip_local_bootstrap:
        bootstrap_local_django = prompt_yes_no(
            'Run local migrate and ensure the admin account now',
            default=True,
            interactive=interactive,
        )

    env_defaults = {
        **existing_defaults,
        'database_name': database_name,
        'database_user': database_user,
        'database_password': database_password,
        'database_host': database_host,
        'database_port': database_port,
        'admin_username': admin_username,
        'admin_email': admin_email,
        'admin_password': admin_password,
    }

    registry_entry = {
        'slug': slug,
        'site_name': site_name,
        'domain': domain,
        'public_url': public_url,
        'settings_module': f'ecatalogus.settings_{slug}',
        'overlay_dir': f'static_{slug}',
        'role': role,
        'peer_id': slug,
        'canonical_master': False,
        'default_parent_peer': default_parent_peer,
        'source_peers': source_peers,
        'project_id': project_id,
        'foreign_id_name': foreign_id_name,
        'local_port': local_port,
        'database_name': database_name,
        'database_user': database_user,
    }

    return {
        'instance': registry_entry,
        'deploy_user': deploy_user,
        'registry': existing_registry,
        'env_defaults': env_defaults,
        'setup_dev_db': setup_dev_db,
        'bootstrap_local_django': bootstrap_local_django,
    }


def ensure_parent(path: Path, dry_run: bool) -> None:
    if dry_run:
        return
    path.parent.mkdir(parents=True, exist_ok=True)


def write_text(path: Path, content: str, dry_run: bool) -> None:
    if dry_run:
        print(f'[dry-run] write {path.relative_to(REPO_ROOT)}')
        return
    ensure_parent(path, dry_run)
    path.write_text(content, encoding='utf-8')


def copy_file(source: Path, target: Path, dry_run: bool) -> None:
    if dry_run:
        print(f'[dry-run] copy {source.relative_to(REPO_ROOT)} -> {target.relative_to(REPO_ROOT)}')
        return
    ensure_parent(target, dry_run)
    shutil.copyfile(source, target)


def update_registry(registry: dict, instance: dict, dry_run: bool) -> None:
    registry.setdefault('instances', {})[instance['slug']] = instance
    write_text(REGISTRY_PATH, dump_registry(registry), dry_run)


def main() -> int:
    parser = argparse.ArgumentParser(description='Create a new multi-instance scaffold without hand-writing files.')
    parser.add_argument('--slug')
    parser.add_argument('--site-name')
    parser.add_argument('--domain')
    parser.add_argument('--deploy-user')
    parser.add_argument('--local-port')
    parser.add_argument('--public-url')
    parser.add_argument('--role', choices=['master', 'slave'])
    parser.add_argument('--default-parent-peer')
    parser.add_argument('--foreign-id-name')
    parser.add_argument('--project-id')
    parser.add_argument('--database-name')
    parser.add_argument('--database-user')
    parser.add_argument('--database-password')
    parser.add_argument('--database-host')
    parser.add_argument('--database-port')
    parser.add_argument('--admin-username')
    parser.add_argument('--admin-email')
    parser.add_argument('--admin-password')
    parser.add_argument('--skip-dev-db-setup', action='store_true')
    parser.add_argument('--skip-local-bootstrap', action='store_true')
    parser.add_argument('--non-interactive', action='store_true')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()

    try:
        collected = collect_instance(not args.non_interactive, args)
    except ValueError as exc:
        print(f'Error: {exc}', file=sys.stderr)
        return 1

    instance = collected['instance']
    deploy_user = collected['deploy_user']
    registry = collected['registry']
    env_defaults = collected['env_defaults']
    setup_dev_db = collected['setup_dev_db']
    bootstrap_local_django = collected['bootstrap_local_django']

    settings_path = REPO_ROOT / 'ecatalogus' / f"settings_{instance['slug']}.py"
    run_script_path = REPO_ROOT / f"run_{instance['slug']}.sh"
    local_env_path = REPO_ROOT / f".env.{instance['slug']}"
    install_env_path = REPO_ROOT / 'scripts' / 'config' / f"{instance['slug']}.env"
    overlay_dir = REPO_ROOT / f"static_{instance['slug']}"

    update_registry(registry, instance, args.dry_run)
    write_text(settings_path, build_settings_module(instance), args.dry_run)
    write_text(run_script_path, build_run_script(instance), args.dry_run)
    write_text(local_env_path, build_instance_env(instance, env_defaults), args.dry_run)
    write_text(install_env_path, build_install_env(instance, deploy_user), args.dry_run)
    write_text(overlay_dir / 'js' / 'config.js', build_js_config(instance), args.dry_run)
    copy_file(BASE_LOGO_PATH, overlay_dir / 'img' / 'logo_flat.svg', args.dry_run)
    copy_file(BASE_ABOUT_PATH, overlay_dir / 'about.html', args.dry_run)

    try:
        if setup_dev_db:
            setup_local_dev_database(instance, env_defaults, dry_run=args.dry_run)
        if bootstrap_local_django:
            run_local_bootstrap(instance, local_env_path, dry_run=args.dry_run)
    except (RuntimeError, ValueError) as exc:
        print(f'Error: {exc}', file=sys.stderr)
        return 1

    print('Generated instance scaffold:')
    print(f'  settings: ecatalogus/settings_{instance["slug"]}.py')
    print(f'  run script: run_{instance["slug"]}.sh')
    print(f'  local env: .env.{instance["slug"]}')
    print(f'  install env: scripts/config/{instance["slug"]}.env')
    print(f'  overlay dir: static_{instance["slug"]}/')
    print(f'  registry: scripts/config/instance_registry.toml')
    print()
    print('Next steps:')
    print(f'  1. Review scripts/config/{instance["slug"]}.env and set REPO_URL / branch / any host-specific paths.')
    print(f'  2. Review .env.{instance["slug"]}; it was regenerated using current saved values as defaults.')
    print(f'  3. Commit repo-owned files, but do not commit .env.{instance["slug"]}.')
    print(f'  4. The local bootstrap step runs migrate and ensures admin {env_defaults["admin_username"]!r} from DJANGO_SUPERUSER_* env values.')
    print(f'  5. Start locally with ./run_{instance["slug"]}.sh.')
    print(f'  6. On the server run scripts/install_instance.sh scripts/config/{instance["slug"]}.env')

    return 0


if __name__ == '__main__':
    raise SystemExit(main())