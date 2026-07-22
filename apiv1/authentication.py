"""Authentication tuned for browser callers on a partner site.

The public API is called from JavaScript running on another origin — the user
types their eCatalogus credentials into a form there and the page sends them as
HTTP Basic. Plain ``BasicAuthentication`` would answer a failed attempt with
``WWW-Authenticate: Basic``, which makes the browser pop up its own native
password dialog on top of the application's form. That dialog cannot be styled,
cannot be cancelled cleanly, and is deeply confusing next to the form the user
just filled in.

Returning a challenge scheme browsers do not recognise keeps the 401 status and
the JSON error body while suppressing the dialog, so the calling page can render
the failure itself.
"""

from drf_spectacular.extensions import OpenApiAuthenticationExtension
from rest_framework.authentication import BasicAuthentication


class SilentBasicAuthentication(BasicAuthentication):
    """HTTP Basic without triggering the browser's built-in login prompt."""

    def authenticate_header(self, request):
        return 'xBasic realm="api"'


class SilentBasicAuthenticationScheme(OpenApiAuthenticationExtension):
    """Teach drf-spectacular that the class above is still plain HTTP Basic.

    Without this the generator cannot resolve a custom authentication class and
    silently drops it, so the published schema would advertise session cookies as
    the only way in — exactly wrong for the integration this API exists to serve.
    """

    target_class = 'apiv1.authentication.SilentBasicAuthentication'
    name = 'basicAuth'

    def get_security_definition(self, auto_schema):
        return {
            'type': 'http',
            'scheme': 'basic',
            'description': (
                'An eCatalogus username and password over HTTPS. This is how an '
                'external system authenticates on behalf of the person using it.'
            ),
        }
