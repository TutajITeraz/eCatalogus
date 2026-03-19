// Instance config — Liturgica Poloniae (MPL)
// This file is loaded before main.js and overrides per-instance settings.
// Served from static_mpl/ overlay, shadows indexerapp/static/js/config.js (if any).

window.SITE_CONFIG = (function () {
    const origin = window.location.origin; // preserves port, e.g. http://127.0.0.1:8080

    // Production URL mapping: if running behind a known production domain,
    // use that as pageRoot; otherwise fall back to current origin (handles local dev).
    const productionRoots = {
        'https://monumenta-poloniae-liturgica.ispan.pl': 'https://monumenta-poloniae-liturgica.ispan.pl',
        'https://lp.hostline.net.pl':                   'https://monumenta-poloniae-liturgica.ispan.pl',
        'https://liturgicapoloniae.hostline.net.pl':     'https://monumenta-poloniae-liturgica.ispan.pl',
        'http://lp.hostline.net.pl':                    'https://monumenta-poloniae-liturgica.ispan.pl',
        'http://liturgicapoloniae.hostline.net.pl':     'https://monumenta-poloniae-liturgica.ispan.pl',
    };

    return {
        pageRoot:         productionRoots[origin] || origin,
        projectId:        2,
        siteName:         'Liturgica Poloniae',
        foreign_id_name:  'MSPL no.',
    };
})();
