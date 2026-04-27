"""Dynamic default settings alias based on DJANGO_SETTINGS_MODULE."""

import importlib
import os


target_module = os.getenv('DJANGO_SETTINGS_MODULE', 'ecatalogus.settings_mpl')
if target_module == 'ecatalogus.settings':
	target_module = os.getenv('DEFAULT_INSTANCE_SETTINGS_MODULE', 'ecatalogus.settings_mpl')

loaded_module = importlib.import_module(target_module)

for attribute_name in dir(loaded_module):
	if attribute_name.isupper():
		globals()[attribute_name] = getattr(loaded_module, attribute_name)
