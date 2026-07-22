import secrets
from dataclasses import dataclass

from django.conf import settings
from drf_spectacular.extensions import OpenApiAuthenticationExtension
from rest_framework import exceptions
from rest_framework.authentication import BaseAuthentication, get_authorization_header


@dataclass
class ETLAPIUser:
    username: str = 'etl-api'

    @property
    def is_authenticated(self):
        return True


class ETLTokenAuthentication(BaseAuthentication):
    keyword_prefixes = ('Token', 'Bearer')

    def authenticate(self, request):
        configured_token = getattr(settings, 'ETL_API_TOKEN', '')
        if not configured_token:
            raise exceptions.AuthenticationFailed('ETL API token is not configured.')

        supplied_token = self._get_supplied_token(request)
        if supplied_token is None:
            return None

        if not secrets.compare_digest(supplied_token, configured_token):
            raise exceptions.AuthenticationFailed('Invalid ETL API token.')

        return (ETLAPIUser(), supplied_token)

    def authenticate_header(self, request):
        return 'Token'

    def _get_supplied_token(self, request):
        explicit_header = request.META.get('HTTP_X_ETL_TOKEN')
        if explicit_header:
            return explicit_header.strip()

        auth_header = get_authorization_header(request).decode('utf-8').strip()
        if not auth_header:
            return None

        parts = auth_header.split(None, 1)
        if len(parts) != 2 or parts[0] not in self.keyword_prefixes:
            raise exceptions.AuthenticationFailed('Unsupported authorization header format.')

        return parts[1].strip()


class ETLTokenAuthenticationScheme(OpenApiAuthenticationExtension):
    """Describe the ETL token in the OpenAPI schema.

    drf-spectacular cannot introspect a custom authentication class, so without
    this the ETL operations were published with no security requirement at all —
    making replication endpoints look unauthenticated to anyone reading the docs.
    """

    target_class = 'etlapp.authentication.ETLTokenAuthentication'
    name = 'etlToken'

    def get_security_definition(self, auto_schema):
        return {
            'type': 'apiKey',
            'in': 'header',
            'name': 'X-ETL-Token',
            'description': (
                'Shared per-instance replication token. Also accepted as '
                '"Authorization: Token <value>" or "Authorization: Bearer <value>". '
                'Internal to eCatalogus deployments — not for third-party use.'
            ),
        }
