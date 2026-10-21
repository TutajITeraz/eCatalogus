"""MySQL/MariaDB backend override.

All ``uuid`` / ``*_uuid`` columns in this project were created as legacy
``CHAR(32)`` hex strings (no dashes), not MariaDB's native ``UUID`` type.

Django's stock MySQL backend detects support for that native type at
connection time (``DatabaseFeatures.has_native_uuid_field``) and, once the
server is MariaDB >= 10.7, starts sending dashed UUID literals for every
filter/join on a UUIDField. Those no longer match our dash-less columns, so
lookups silently return zero rows on newer MariaDB while working fine on
10.6 -- e.g. production (10.6) vs a locally installed MariaDB (12.x).

Forcing the flag off keeps Django on the dash-less (``.hex``) code path
everywhere, matching the actual column format on every MariaDB version we
run against.

Case-insensitive lookups: ``icontains`` & co. compile to a plain ``LIKE``, whose
case sensitivity follows the column collation. A database imported from a
``utf8mb4_bin`` dump (eCLLA) therefore finds "Karlsruhe" but not "kar". The
``*_unicode_ci`` collation is attached to the *pattern*, which (being explicit)
overrides the column's, so the search behaves the same on every instance. Set
``CASE_INSENSITIVE_LOOKUPS = False`` in the DATABASES entry to turn it off.
"""

from django.db.backends.mysql import base as mysql_base


class DatabaseFeatures(mysql_base.DatabaseFeatures):
    has_native_uuid_field = False


_CI = ' COLLATE utf8mb4_unicode_ci'
CASE_INSENSITIVE_OPERATORS = {
    **mysql_base.DatabaseWrapper.operators,
    **{
        name: mysql_base.DatabaseWrapper.operators[name] + _CI
        for name in ('iexact', 'icontains', 'istartswith', 'iendswith')
    },
}


class DatabaseWrapper(mysql_base.DatabaseWrapper):
    features_class = DatabaseFeatures

    def __init__(self, settings_dict, *args, **kwargs):
        super().__init__(settings_dict, *args, **kwargs)
        if settings_dict.get('CASE_INSENSITIVE_LOOKUPS', True):
            self.operators = CASE_INSENSITIVE_OPERATORS
