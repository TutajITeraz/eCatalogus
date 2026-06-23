"""Dynamic default settings alias based on DJANGO_SETTINGS_MODULE."""

import importlib
import os

from ecatalogus.env_loader import resolve_runtime_instance_slug

target_module = os.getenv('DJANGO_SETTINGS_MODULE', '').strip()
if not target_module or target_module == 'ecatalogus.settings':
	instance_slug = resolve_runtime_instance_slug(target_module)
	if instance_slug:
		target_module = f'ecatalogus.settings_{instance_slug}'
	else:
		target_module = os.getenv('DEFAULT_INSTANCE_SETTINGS_MODULE', '').strip()

if not target_module:
	raise RuntimeError('DJANGO_SETTINGS_MODULE must be set to an instance-specific settings module.')

if target_module in {'ecatalogus.settings', 'ritus_indexer.settings'}:
	raise RuntimeError('Refusing to load a generic Django settings alias without an explicit INSTANCE_SLUG.')

loaded_module = importlib.import_module(target_module)

for attribute_name in dir(loaded_module):
	if attribute_name.isupper():
		globals()[attribute_name] = getattr(loaded_module, attribute_name)
