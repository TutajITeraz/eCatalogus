from pathlib import Path
import os

from dotenv import load_dotenv


def resolve_runtime_instance_slug(settings_module=None):
    """Infer the active instance slug from explicit runtime settings."""
    settings_module = settings_module or os.getenv('DJANGO_SETTINGS_MODULE', '')

    instance_slug = os.getenv('INSTANCE_SLUG', '').strip()

    module_name = settings_module.rsplit('.', 1)[-1]
    module_slug = ''
    if module_name.startswith('settings_'):
        module_slug = module_name[len('settings_') :]

    if instance_slug and module_slug and instance_slug != module_slug:
        raise RuntimeError(
            f'INSTANCE_SLUG ({instance_slug}) does not match DJANGO_SETTINGS_MODULE ({settings_module}).'
        )

    if instance_slug:
        return instance_slug

    if module_slug:
        return module_slug

    return ''


def load_runtime_env(settings_module=None):
    """Load local .env files before Django boots, including instance overrides."""
    base_dir = Path(__file__).resolve().parent.parent
    settings_module = settings_module or os.getenv('DJANGO_SETTINGS_MODULE', '')

    base_env = base_dir / '.env'
    if base_env.exists():
        load_dotenv(base_env, override=False)

    instance_slug = resolve_runtime_instance_slug(settings_module)
    if instance_slug:
        instance_env = base_dir / f'.env.{instance_slug}'
        if instance_env.exists():
            load_dotenv(instance_env, override=False)

    return os.getenv('DJANGO_SETTINGS_MODULE', settings_module)
