const colorPalette = [
    '#e6194B', '#3cb44b', '#ffe119', '#4363d8', '#f58231',
    '#911eb4', '#42d4f4', '#f032e6', '#bfef45', '#fabed4',
    '#469990', '#dcbeff', '#9A6324', '#fffac8', '#800000',
    '#aaffc3', '#808000', '#ffd8b1'
];

const EXPORT_SCALE = 1.5;

let lastFormulasData = [];
let traditionColors = {
    Multiple: '#000075',
    Unattributed: '#a9a9a9'
};
let traditionMap = {};
let currentChartType = 'parallel';

function assignTraditionColor(traditionName, preferredIndex) {
    if (traditionColors[traditionName]) {
        return traditionColors[traditionName];
    }

    const usedColors = new Set(Object.values(traditionColors));
    const preferredColor = typeof preferredIndex === 'number'
        ? colorPalette[preferredIndex % colorPalette.length]
        : null;

    if (preferredColor && !usedColors.has(preferredColor)) {
        traditionColors[traditionName] = preferredColor;
        return preferredColor;
    }

    const fallbackColor = colorPalette.find(color => !usedColors.has(color))
        || colorPalette[Object.keys(traditionColors).length % colorPalette.length];

    traditionColors[traditionName] = fallbackColor;
    return fallbackColor;
}

ms_formulas_graph_init = function() {
    let originalData = [];
    let leftId = -1;
    let rightId = -1;

    $('#traditionFilter').select2();
    $('#genreSelect').select2({
        ajax: {
            url: pageRoot + '/liturgical-genres-autocomplete/',
            dataType: 'json',
            xhrFields: {
                withCredentials: true
            },
            processResults: function(data) {
                return {
                    results: data.results,
                    pagination: data.pagination
                };
            }
        }
    });

    $('#chartTypeSelect').select2({
        minimumResultsForSearch: Infinity,
        data: [
            { id: 'parallel', text: 'Parallel Coordinates Plot' },
            { id: 'dot_matrix', text: 'Dot Plot Matrix' },
            { id: 'circos', text: 'Circos Plot' },
            { id: 'sankey', text: 'Sankey Diagram' }
        ]
    });
    $('#chartTypeSelect').val(currentChartType).trigger('change');

    function configureTraditionFilter(genreId) {
        $('#traditionFilter').val(null).trigger('change');
        $('#traditionFilter').select2({
            ajax: {
                url: pageRoot + '/traditions-autocomplete/?genre=' + genreId,
                dataType: 'json',
                xhrFields: {
                    withCredentials: true
                },
                processResults: function(data) {
                    traditionMap = {};
                    data.results.forEach((tradition, index) => {
                        traditionMap[tradition.id] = tradition.text;
                        assignTraditionColor(tradition.text, index);
                    });
                    traditionMap.Unattributed = 'Unattributed';
                    data.results.push({ id: 'Unattributed', text: 'Unattributed' });
                    return {
                        results: data.results,
                        pagination: data.pagination
                    };
                }
            }
        });
    }

    function selectInitialGenre() {
        $.ajax({
            url: pageRoot + '/liturgical-genres-autocomplete/',
            dataType: 'json',
            xhrFields: {
                withCredentials: true
            }
        }).done(function(data) {
            const firstGenre = data?.results?.[0];
            if (!firstGenre || $('#genreSelect').val()) {
                return;
            }

            const option = new Option(firstGenre.text, firstGenre.id, true, true);
            $('#genreSelect').append(option).trigger('change');
            configureTraditionFilter(firstGenre.id);
        });
    }

    function setTableHeight() {
        const windowHeight = $(window).height();
        const windowWidth = $(window).width();
        const tableHeight = windowWidth > 640 ? windowHeight - 400 : windowHeight - 370;
        $('#chart').css('height', tableHeight + 'px');
    }

    function showSpinner(text) {
        $('#chart').html(`<div class="text-center py-10 text-gray-600 font-semibold">${text}...</div>`);
    }

    function showEmptyGraph(message) {
        $('#chart').html(`<div class="text-center py-10 text-gray-600 font-semibold">${message}</div>`);
    }

    function renderActiveChart(data) {
        lastFormulasData = data;
        currentChartType = $('#chartTypeSelect').val() || 'parallel';

        if (!data.length) {
            showEmptyGraph('No data available for the selected filters.');
            return;
        }

        window.FormulasVisualizations.render({
            type: currentChartType,
            containerSelector: '#chart',
            data,
            colorizeTraditions: $('#colorizeTraditions').is(':checked'),
            traditionColors,
            colorPalette
        });
    }

    function renderFilteredChart() {
        showSpinner('Updating graph');
        const selectedIds = $('#traditionFilter').val() || [];
        const selectedTraditions = selectedIds.map(id => traditionMap[id] || id);
        let filteredData = originalData;

        if (selectedTraditions.length > 0) {
            filteredData = originalData.filter(item => {
                const traditions = item.formula_traditions || [];
                if (selectedTraditions.includes('Unattributed') && selectedTraditions.length === 1) {
                    return traditions.length === 0;
                }
                if (selectedTraditions.includes('Unattributed')) {
                    return traditions.length === 0 || selectedTraditions.some(tradition => tradition !== 'Unattributed' && traditions.includes(tradition));
                }
                return selectedTraditions.some(tradition => traditions.includes(tradition));
            });
        }

        renderActiveChart(filteredData);
    }

    function fetchDataAndDrawChart(left, right) {
        if (left === -1 || right === -1) {
            return;
        }

        showSpinner('Data loading');

        fetch(pageRoot + '/compare_formulas_json/?left=' + left + '&right=' + right)
            .then(response => response.json())
            .then(data => {
                originalData = data;
                const allTraditions = new Set();
                data.forEach(item => {
                    (item.formula_traditions || []).forEach(tradition => allTraditions.add(tradition));
                });

                allTraditions.forEach(tradition => assignTraditionColor(tradition));

                showStats(originalData);
                renderFilteredChart();
            })
            .catch(() => {
                showEmptyGraph('Could not load graph data.');
            });
    }

    function showStats(data) {
        const container = document.getElementById('ms_stats');
        container.innerHTML = '';

        const manuscriptGroups = {};
        const allFormulaIds = new Map();
        const allFormulaTraditions = new Map();
        const allTraditions = new Set();

        for (const item of data) {
            const manuscript = item.Table;
            if (!manuscriptGroups[manuscript]) {
                manuscriptGroups[manuscript] = [];
            }
            manuscriptGroups[manuscript].push(item);

            if (!allFormulaIds.has(item.formula_id)) {
                allFormulaIds.set(item.formula_id, new Set());
            }
            allFormulaIds.get(item.formula_id).add(manuscript);

            if (!allFormulaTraditions.has(item.formula_id)) {
                allFormulaTraditions.set(item.formula_id, new Set());
            }
            (item.formula_traditions || []).forEach(tradition => {
                allFormulaTraditions.get(item.formula_id).add(tradition);
                allTraditions.add(tradition);
            });
        }

        const manuscriptStats = [];
        const traditionCounts = {};
        allTraditions.forEach(tradition => {
            traditionCounts[tradition] = { only: 0, count: 0 };
        });
        traditionCounts.Multiple = { only: 0, count: 0 };
        traditionCounts.Unattributed = { only: 0, count: 0 };

        for (const [manuscript, entries] of Object.entries(manuscriptGroups)) {
            const stats = { manuscript, total: entries.length, unattributed: 0, Multiple: 0 };
            allTraditions.forEach(tradition => {
                stats[tradition] = 0;
                stats[`${tradition}_only`] = 0;
            });

            for (const entry of entries) {
                const traditions = new Set(entry.formula_traditions || []);
                if (traditions.size === 0) {
                    stats.unattributed += 1;
                    traditionCounts.Unattributed.count += 1;
                } else if (traditions.size > 1) {
                    stats.Multiple += 1;
                    traditionCounts.Multiple.count += 1;
                } else {
                    const tradition = Array.from(traditions)[0];
                    stats[tradition] += 1;
                    stats[`${tradition}_only`] += 1;
                    traditionCounts[tradition].count += 1;
                    traditionCounts[tradition].only += 1;
                }
            }

            manuscriptStats.push(stats);
        }

        const sharedStats = {};
        allTraditions.forEach(tradition => {
            sharedStats[tradition] = 0;
        });
        sharedStats.Multiple = 0;
        sharedStats.Unattributed = 0;

        let totalShared = 0;
        for (const [formulaId, manuscripts] of allFormulaIds.entries()) {
            if (manuscripts.size <= 1) {
                continue;
            }

            totalShared += 1;
            const traditions = allFormulaTraditions.get(formulaId) || new Set();
            if (traditions.size === 0) {
                sharedStats.Unattributed += 1;
            } else if (traditions.size > 1) {
                sharedStats.Multiple += 1;
            } else {
                sharedStats[Array.from(traditions)[0]] += 1;
            }
        }

        let html = '<div class="space-y-6">';
        manuscriptStats.forEach(stat => {
            html += `
                <div class="border border-gray-300 rounded-lg p-4 bg-white shadow-md">
                    <h3 class="text-lg font-semibold text-gray-800 mb-2">${stat.manuscript}</h3>
                    <ul class="text-sm text-gray-700 space-y-1">
                        <li><span class="font-medium">Total orations:</span> ${stat.total}</li>`;
            allTraditions.forEach(tradition => {
                if (stat[tradition] > 0) {
                    html += `<li><span class="dot" style="background-color: ${traditionColors[tradition] || '#6b7280'};"></span><span class="font-medium">${tradition}:</span> ${stat[tradition]}</li>`;
                }
            });
            if (stat.Multiple > 0) {
                html += `<li><span class="dot" style="background-color: ${traditionColors.Multiple};"></span><span class="font-medium">Multiple traditions:</span> ${stat.Multiple}</li>`;
            }
            html += `<li><span class="dot" style="background-color: ${traditionColors.Unattributed};"></span><span class="font-medium">Unattributed:</span> ${stat.unattributed}</li>
                    </ul>
                </div>`;
        });

        html += `
            <div class="border border-gray-300 rounded-lg p-4 bg-yellow-50 shadow-inner">
                <h3 class="text-lg font-semibold text-yellow-900 mb-2">Global Stats</h3>
                <ul class="text-sm text-yellow-800 space-y-1">
                    <li><span class="font-medium">Number of connections between manuscripts:</span> ${totalShared}</li>`;
        allTraditions.forEach(tradition => {
            if (sharedStats[tradition] > 0) {
                html += `<li><span class="dot" style="background-color: ${traditionColors[tradition] || '#6b7280'};"></span><span class="font-medium">${tradition}:</span> ${sharedStats[tradition]}</li>`;
            }
        });
        if (sharedStats.Multiple > 0) {
            html += `<li><span class="dot" style="background-color: ${traditionColors.Multiple};"></span><span class="font-medium">Multiple traditions:</span> ${sharedStats.Multiple}</li>`;
        }
        html += `<li><span class="dot" style="background-color: ${traditionColors.Unattributed};"></span><span class="font-medium">Unattributed:</span> ${sharedStats.Unattributed}</li>
                </ul>
            </div>
        </div>`;

        container.innerHTML = html;
    }

    function getCurrentChartSvgClone() {
        const svg = document.querySelector('#chart svg');
        if (!svg) {
            return null;
        }

        const clone = svg.cloneNode(true);
        clone.setAttribute('xmlns', 'http://www.w3.org/2000/svg');
        const hasBackground = Array.from(clone.children).some(node => node.tagName === 'rect' && node.getAttribute('fill') === 'white');
        if (!hasBackground) {
            const width = clone.getAttribute('width') || svg.clientWidth;
            const height = clone.getAttribute('height') || svg.clientHeight;
            const background = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
            background.setAttribute('width', width);
            background.setAttribute('height', height);
            background.setAttribute('fill', 'white');
            clone.insertBefore(background, clone.firstChild);
        }
        return clone;
    }

    function downloadBlob(blob, filename) {
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = filename;
        link.click();
        setTimeout(() => URL.revokeObjectURL(url), 1000);
    }

    setTableHeight();
    $(window).resize(setTableHeight);
    selectInitialGenre();

    $('.manuscript_filter_left').select2({
        ajax: {
            url: pageRoot + '/manuscripts-autocomplete/',
            dataType: 'json',
            xhrFields: {
                withCredentials: true
            }
        }
    });

    $('.manuscript_filter_right').select2({
        ajax: {
            url: pageRoot + '/manuscripts-autocomplete/',
            dataType: 'json',
            xhrFields: {
                withCredentials: true
            }
        }
    });

    $('#genreSelect').on('select2:select', function(event) {
        configureTraditionFilter(event.params.data.id);
    });

    $('#traditionFilter').on('change', renderFilteredChart);
    $('#colorizeTraditions').on('change', renderFilteredChart);
    $('#chartTypeSelect').on('change', function() {
        currentChartType = $(this).val() || 'parallel';
        if (originalData.length) {
            renderFilteredChart();
        }
    });

    $('.manuscript_filter_left').on('select2:select', function(event) {
        leftId = event.params.data.id;
        fetchDataAndDrawChart(leftId, rightId);
    });

    $('.manuscript_filter_right').on('select2:select', function(event) {
        rightId = event.params.data.id;
        fetchDataAndDrawChart(leftId, rightId);
    });
};

window.exportFormulasSvg = function() {
    if (!lastFormulasData.length) {
        alert('No data to export');
        return;
    }

    const svg = document.querySelector('#chart svg');
    if (!svg) {
        alert('No graph to export');
        return;
    }

    const clone = svg.cloneNode(true);
    clone.setAttribute('xmlns', 'http://www.w3.org/2000/svg');
    const hasBackground = Array.from(clone.children).some(node => node.tagName === 'rect' && node.getAttribute('fill') === 'white');
    if (!hasBackground) {
        const background = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
        background.setAttribute('width', clone.getAttribute('width') || svg.clientWidth);
        background.setAttribute('height', clone.getAttribute('height') || svg.clientHeight);
        background.setAttribute('fill', 'white');
        clone.insertBefore(background, clone.firstChild);
    }

    const svgString = new XMLSerializer().serializeToString(clone);
    const url = URL.createObjectURL(new Blob([svgString], { type: 'image/svg+xml' }));
    const link = document.createElement('a');
    link.href = url;
    link.download = 'formulas_graph.svg';
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
};

window.exportFormulasPng = function() {
    if (!lastFormulasData.length) {
        alert('No data to export');
        return;
    }

    const svg = document.querySelector('#chart svg');
    if (!svg) {
        alert('No graph to export');
        return;
    }

    const clone = svg.cloneNode(true);
    clone.setAttribute('xmlns', 'http://www.w3.org/2000/svg');
    const hasBackground = Array.from(clone.children).some(node => node.tagName === 'rect' && node.getAttribute('fill') === 'white');
    if (!hasBackground) {
        const background = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
        background.setAttribute('width', clone.getAttribute('width') || svg.clientWidth);
        background.setAttribute('height', clone.getAttribute('height') || svg.clientHeight);
        background.setAttribute('fill', 'white');
        clone.insertBefore(background, clone.firstChild);
    }

    const svgString = new XMLSerializer().serializeToString(clone);
    const svgWidth = parseInt(clone.getAttribute('width'), 10);
    const svgHeight = parseInt(clone.getAttribute('height'), 10);
    const canvas = document.createElement('canvas');
    canvas.width = svgWidth * EXPORT_SCALE;
    canvas.height = svgHeight * EXPORT_SCALE;
    const context = canvas.getContext('2d');
    context.scale(EXPORT_SCALE, EXPORT_SCALE);
    context.fillStyle = 'white';
    context.fillRect(0, 0, svgWidth, svgHeight);
    const image = new Image();
    const url = URL.createObjectURL(new Blob([svgString], { type: 'image/svg+xml' }));
    image.onload = function() {
        context.drawImage(image, 0, 0);
        URL.revokeObjectURL(url);
        const link = document.createElement('a');
        link.download = 'formulas_graph.png';
        link.href = canvas.toDataURL('image/png');
        link.click();
    };
    image.src = url;
};

window.exportFormulasJson = function() {
    if (!lastFormulasData.length) {
        alert('No data to export');
        return;
    }

    const url = URL.createObjectURL(new Blob([JSON.stringify(lastFormulasData, null, 2)], { type: 'application/json' }));
    const link = document.createElement('a');
    link.href = url;
    link.download = 'formulas_data.json';
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
};

window.exportFormulasCsv = function() {
    if (!lastFormulasData.length) {
        alert('No data to export');
        return;
    }

    const keys = Object.keys(lastFormulasData[0]);
    const rows = [
        keys.join(','),
        ...lastFormulasData.map(row => keys.map(key => {
            const value = row[key];
            return JSON.stringify(Array.isArray(value) ? value.join(';') : (value ?? ''));
        }).join(','))
    ];

    const url = URL.createObjectURL(new Blob([rows.join('\n')], { type: 'text/csv' }));
    const link = document.createElement('a');
    link.href = url;
    link.download = 'formulas_data.csv';
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
};
