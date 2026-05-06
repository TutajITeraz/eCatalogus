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
        features: {
            sourceProject: false,
            sourceProjectFilter: false,
        },
        uiVisibility: {
            menu: {
                about: true,
                manuscripts: true,
                contentAnalysis: true,
                aiTools: true,
            },
            manuscriptFilters: {
                mainInfo: true,
                layout: true,
                binding: true,
                condition: true,
                content: true,
                musicology: true,
                decoration: true,
                bibliography: true,
            },
            manuscriptSections: {
                mainInfo: true,
                clla: true,
                codicology: true,
                watermarks: true,
                quires: true,
                layouts: true,
                scripts: true,
                mainHands: true,
                additionHands: true,
                musicNotation: true,
                binding: true,
                decoration: true,
                initials: true,
                miniatures: true,
                bordersOthers: true,
                condition: true,
                content: true,
                history: true,
                originsDating: true,
                provenanceHistory: true,
                bibliography: true,
            },
        },
    };
})();
