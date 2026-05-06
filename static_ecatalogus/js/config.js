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
        features: {
            sourceProject: true,
            sourceProjectFilter: true,
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
