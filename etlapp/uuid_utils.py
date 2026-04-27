import uuid


LEGACY_SYNC_UUID_NAMESPACE = uuid.UUID('8e7f6f8a-cc0f-4e6f-a7af-c7a7e9d1f4e3')


def build_deterministic_sync_uuid(model_label, source_pk, namespace=LEGACY_SYNC_UUID_NAMESPACE):
    return uuid.uuid5(namespace, f'{model_label}:{source_pk}')