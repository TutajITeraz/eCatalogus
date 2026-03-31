import secrets
from dataclasses import dataclass

from django.conf import settings
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