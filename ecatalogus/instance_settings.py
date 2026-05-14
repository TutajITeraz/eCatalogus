from pathlib import Path
import os
import tomllib


def _env_prefix_for(instance_slug):
    return instance_slug.upper().replace('-', '_')


def infer_instance_slug(settings_module, default=''):
    module_name = (settings_module or '').rsplit('.', 1)[-1]
    if module_name.startswith('settings_'):
        return module_name[len('settings_'):]
    return default


def _title_from_slug(value):
    return value.replace('-', ' ').replace('_', ' ').title()


def _csv(items):
    return ','.join(item for item in items if item)


def load_instance_registry(base_dir, registry_path=None):
    path = Path(registry_path or (base_dir / 'scripts' / 'config' / 'instance_registry.toml'))
    if not path.exists():
        return {}

    with path.open('rb') as handle:
        payload = tomllib.load(handle)

    return payload.get('instances', {})


def _env_value(*names):
    for name in names:
        value = os.getenv(name, '').strip()
        if value:
            return value
    return ''


def _normalize_url(url):
    if not url:
        return ''
    return str(url).rstrip('/')


def _peer_url(registry, peer_id):
    if not peer_id:
        return ''
    peer_entry = registry.get(peer_id, {})
    return _normalize_url(peer_entry.get('public_url') or peer_entry.get('etl_url'))


def build_registry_peer_token_map(*, env_prefix, registry, source_peers, default_parent_peer=''):
    peer_tokens = {}

    for peer_id in source_peers:
        peer_entry = registry.get(peer_id, {})
        peer_url = _peer_url(registry, peer_id)
        if not peer_url:
            continue

        peer_env_prefix = _env_prefix_for(peer_entry.get('peer_id') or peer_id)
        candidate_names = [
            f'{env_prefix}_ETL_{peer_env_prefix}_API_TOKEN',
            f'{env_prefix}_TO_{peer_env_prefix}_ETL_API_TOKEN',
            f'ETL_{peer_env_prefix}_API_TOKEN',
            f'{peer_env_prefix}_ETL_API_TOKEN',
        ]
        if peer_id == default_parent_peer or peer_entry.get('role') == 'master' or peer_entry.get('canonical_master'):
            candidate_names = [
                f'{env_prefix}_ETL_MASTER_API_TOKEN',
                'ETL_MASTER_API_TOKEN',
                *candidate_names,
            ]

        token = _env_value(*candidate_names)
        if token:
            peer_tokens[peer_url] = token

    return peer_tokens


def apply_instance_settings(settings_globals, *, instance_slug, defaults=None):
    defaults = defaults or {}
    base_dir = settings_globals['BASE_DIR']
    csv_env = settings_globals['csv_env']
    bool_env = settings_globals['bool_env']

    registry_path = defaults.get('registry_path') or (base_dir / 'scripts' / 'config' / 'instance_registry.toml')
    registry = load_instance_registry(base_dir, registry_path)
    registry_entry = dict(registry.get(instance_slug, {})) if registry else {}
    resolved_defaults = {**registry_entry, **defaults}

    env_prefix = resolved_defaults.get('env_prefix') or _env_prefix_for(instance_slug)
    site_name = resolved_defaults.get('site_name') or _title_from_slug(instance_slug)
    overlay_dir = resolved_defaults.get('overlay_dir') or f'static_{instance_slug}'
    default_database_name = resolved_defaults.get('database_name') or instance_slug
    default_database_user = resolved_defaults.get('database_user') or default_database_name
    default_allowed_hosts = resolved_defaults.get('allowed_hosts') or [
        resolved_defaults.get('domain', ''),
        '127.0.0.1',
        'localhost',
    ]
    default_csrf_trusted_origins = resolved_defaults.get('csrf_trusted_origins') or [
        f"https://{resolved_defaults.get('domain', '')}" if resolved_defaults.get('domain') else '',
        f"http://{resolved_defaults.get('domain', '')}" if resolved_defaults.get('domain') else '',
        'https://127.0.0.1',
        'http://127.0.0.1',
    ]
    default_cors_allowed_origins = resolved_defaults.get('cors_allowed_origins') or [
        'http://localhost:3000',
        'http://localhost:8000',
        f"https://{resolved_defaults.get('domain', '')}" if resolved_defaults.get('domain') else '',
        f"http://{resolved_defaults.get('domain', '')}" if resolved_defaults.get('domain') else '',
    ]
    media_root_env_name = resolved_defaults.get('media_root_env_name') or f'{env_prefix}_MEDIA_ROOT'
    default_media_root = resolved_defaults.get('media_root') or str(base_dir / 'media_instances' / instance_slug)
    default_role = resolved_defaults.get('role', 'slave')
    default_canonical_master_id = resolved_defaults.get('canonical_master_id') or 'ecatalogus'
    default_registry_path = str(registry_path)
    default_peer_id = resolved_defaults.get('peer_id') or instance_slug
    default_local_url = resolved_defaults.get('public_url') or ''
    default_database_options = resolved_defaults.get('database_options') or {}

    default_source_peers = list(resolved_defaults.get('source_peers') or [])
    if not default_source_peers and default_role == 'master' and registry:
        default_source_peers = [peer_id for peer_id in registry.keys() if peer_id != instance_slug]

    default_parent_peer = resolved_defaults.get('default_parent_peer') or ''
    if not default_parent_peer and default_role != 'master' and default_canonical_master_id in registry:
        default_parent_peer = default_canonical_master_id
    if default_parent_peer and default_parent_peer not in default_source_peers:
        default_source_peers = [default_parent_peer, *default_source_peers]

    explicit_master_url = resolved_defaults.get('master_url')
    if explicit_master_url is None and default_role != 'master':
        explicit_master_url = _peer_url(registry, default_parent_peer)

    explicit_slave_urls = list(resolved_defaults.get('slave_urls') or [])
    if not explicit_slave_urls and default_role == 'master':
        explicit_slave_urls = [_peer_url(registry, peer_id) for peer_id in default_source_peers]
        explicit_slave_urls = [url for url in explicit_slave_urls if url]

    configured_source_peers = csv_env(
        f'{env_prefix}_ETL_SOURCE_PEERS',
        os.getenv('ETL_SOURCE_PEERS', _csv(default_source_peers)),
    )
    configured_default_parent_peer = os.getenv(
        f'{env_prefix}_ETL_DEFAULT_PARENT_PEER',
        os.getenv('ETL_DEFAULT_PARENT_PEER', default_parent_peer),
    )
    if configured_default_parent_peer and configured_default_parent_peer not in configured_source_peers:
        configured_source_peers = [configured_default_parent_peer, *configured_source_peers]

    etl_master_url = os.getenv(f'{env_prefix}_ETL_MASTER_URL', os.getenv('ETL_MASTER_URL', explicit_master_url or '')) or None
    etl_slave_urls = csv_env(
        f'{env_prefix}_ETL_SLAVE_URLS',
        os.getenv('ETL_SLAVE_URLS', _csv(explicit_slave_urls)),
    )
    etl_api_token = os.getenv(
        f'{env_prefix}_ETL_API_TOKEN',
        os.getenv('ETL_API_TOKEN', f'{instance_slug}-token-change-me'),
    )
    etl_peer_tokens = build_registry_peer_token_map(
        env_prefix=env_prefix,
        registry=registry,
        source_peers=configured_source_peers,
        default_parent_peer=configured_default_parent_peer,
    )

    database_config = {
        'ENGINE': 'django.db.backends.mysql',
        'CONN_MAX_AGE': 0,
        'NAME': os.getenv(f'{env_prefix}_DATABASE_NAME', os.getenv('DATABASE_NAME', default_database_name)),
        'USER': os.getenv(f'{env_prefix}_DATABASE_USER', os.getenv('DATABASE_USER', default_database_user)),
        'PASSWORD': os.getenv(f'{env_prefix}_DATABASE_PASSWORD', os.getenv('DATABASE_PASSWORD', '')),
        'HOST': os.getenv(f'{env_prefix}_DATABASE_HOST', os.getenv('DATABASE_HOST', '127.0.0.1')),
        'PORT': os.getenv(f'{env_prefix}_DATABASE_PORT', os.getenv('DATABASE_PORT', '3306')),
    }
    if default_database_options:
        database_config['OPTIONS'] = default_database_options

    settings_globals.update({
        'INSTANCE_SLUG': instance_slug,
        'INSTANCE_ENV_PREFIX': env_prefix,
        'SECRET_KEY': os.getenv(
            f'{env_prefix}_SECRET_KEY',
            os.getenv('SECRET_KEY', f'{instance_slug}-secret-key-change-me'),
        ),
        'DEBUG': bool_env(f'{env_prefix}_DEBUG', os.getenv('DEBUG', '0')),
        'ALLOWED_HOSTS': csv_env(
            f'{env_prefix}_ALLOWED_HOSTS',
            os.getenv('ALLOWED_HOSTS', _csv(default_allowed_hosts)),
        ),
        'CSRF_TRUSTED_ORIGINS': csv_env(
            f'{env_prefix}_CSRF_TRUSTED_ORIGINS',
            os.getenv('CSRF_TRUSTED_ORIGINS', _csv(default_csrf_trusted_origins)),
        ),
        'CORS_ALLOWED_ORIGINS': csv_env(
            f'{env_prefix}_CORS_ALLOWED_ORIGINS',
            os.getenv('CORS_ALLOWED_ORIGINS', _csv(default_cors_allowed_origins)),
        ),
        'DATABASES': {'default': database_config},
        'STATICFILES_DIRS': [
            base_dir / overlay_dir,
            base_dir / 'static_assets',
            base_dir / 'indexerapp/static',
        ],
        'MEDIA_ROOT': os.getenv(media_root_env_name, os.getenv('MEDIA_ROOT', default_media_root)),
        'SITE_NAME': site_name,
        'PROJECT_ID': defaults.get('project_id', 0),
        'FOREIGN_ID_NAME': defaults.get('foreign_id_name', 'foreign id'),
        'SESSION_COOKIE_NAME': os.getenv(
            f'{env_prefix}_SESSION_COOKIE_NAME',
            os.getenv('SESSION_COOKIE_NAME', defaults.get('session_cookie_name', f'{instance_slug}_sessionid')),
        ),
        'CSRF_COOKIE_NAME': os.getenv(
            f'{env_prefix}_CSRF_COOKIE_NAME',
            os.getenv('CSRF_COOKIE_NAME', defaults.get('csrf_cookie_name', f'{instance_slug}_csrftoken')),
        ),
        'ETL_ROLE': os.getenv(f'{env_prefix}_ETL_ROLE', os.getenv('ETL_ROLE', default_role)),
        'ETL_MASTER_URL': etl_master_url,
        'ETL_SLAVE_URLS': etl_slave_urls,
        'ETL_API_TOKEN': etl_api_token,
        'ETL_PEER_TOKENS': etl_peer_tokens,
        'ETL_SELF_PEER_ID': os.getenv(f'{env_prefix}_ETL_SELF_PEER_ID', os.getenv('ETL_SELF_PEER_ID', default_peer_id)),
        'ETL_SOURCE_PEERS': configured_source_peers,
        'ETL_DEFAULT_PARENT_PEER': configured_default_parent_peer,
        'ETL_CANONICAL_MASTER_ID': os.getenv(
            f'{env_prefix}_ETL_CANONICAL_MASTER_ID',
            os.getenv('ETL_CANONICAL_MASTER_ID', default_canonical_master_id),
        ),
        'ETL_PEER_REGISTRY_PATH': os.getenv(
            f'{env_prefix}_ETL_PEER_REGISTRY_PATH',
            os.getenv('ETL_PEER_REGISTRY_PATH', default_registry_path),
        ),
        'INSTANCE_PUBLIC_URL': os.getenv(
            f'{env_prefix}_PUBLIC_URL',
            os.getenv('INSTANCE_PUBLIC_URL', default_local_url),
        ),
    })