from django.conf import settings


def site_info(request):
    """Inject site identity variables into every template context."""
    return {
        'SITE_NAME': getattr(settings, 'SITE_NAME', 'eCatalogus'),
        'SITE_SUBTITLE': getattr(settings, 'SITE_SUBTITLE', ''),
    }
