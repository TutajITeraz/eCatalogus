from pathlib import Path
import os

from dotenv import load_dotenv


def resolve_runtime_instance_slug(settings_module=None):
    """Infer the active instance slug from Django settings or service env."""
    settings_module = settings_module or os.getenv('DJANGO_SETTINGS_MODULE', 'ecatalogus.settings')

    module_name = settings_module.rsplit('.', 1)[-1]
    if module_name.startswith('settings_'):
        return module_name[len('settings_') :]

    service_shortname = os.getenv('SERVICE_SHORTNAME', '').strip()
    if service_shortname:
        return service_shortname

    return ''


def load_runtime_env(settings_module=None):
    """Load local .env files before Django boots, including instance overrides."""
    base_dir = Path(__file__).resolve().parent.parent
    settings_module = settings_module or os.getenv('DJANGO_SETTINGS_MODULE', 'ecatalogus.settings')
    instance_slug = resolve_runtime_instance_slug(settings_module)

    candidates = [base_dir / '.env']
    if instance_slug:
        candidates.append(base_dir / f'.env.{instance_slug}')

    for candidate in candidates:
        if candidate.exists():
            load_dotenv(candidate, override=False)

    return settings_module
