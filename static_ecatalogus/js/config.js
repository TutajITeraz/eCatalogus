// Instance config — eCatalogus (master)
// This file is loaded before main.js and overrides per-instance settings.
// Served from static_ecatalogus/ overlay, shadows indexerapp/static/js/config.js (if any).

window.SITE_CONFIG = (function () {
    const origin = window.location.origin; // preserves port, e.g. http://127.0.0.1:8000

    // Production URL mapping: fill in when production domain is assigned.
    const productionRoots = {
        // 'https://ecatalogus.example.pl': 'https://ecatalogus.example.pl',
        'https://eclla.hostline.net.pl': 'https://eclla.hostline.net.pl',
    };

    return {
        pageRoot:         productionRoots[origin] || origin,
        projectId:        0,   // 0 = All; update when eCatalogus gets its own projectId
        siteName:         'eCatalogus',
        foreign_id_name:  'foreign id',
    };
})();
