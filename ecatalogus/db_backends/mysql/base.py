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
"""

from django.db.backends.mysql import base as mysql_base


class DatabaseFeatures(mysql_base.DatabaseFeatures):
    has_native_uuid_field = False


class DatabaseWrapper(mysql_base.DatabaseWrapper):
    features_class = DatabaseFeatures
