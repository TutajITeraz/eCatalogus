const EXPORT_SCALE = 1.5;

let lastEditionData = [];
let currentEditionChartType = 'parallel';

ms_edition_graph_init = function() {
    let originalData = [];

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
        lastEditionData = data;
        currentEditionChartType = $('#editionChartTypeSelect').val() || 'parallel';

        if (!data.length) {
            showEmptyGraph('No data available for the selected manuscripts.');
            return;
        }

        window.EditionVisualizations.render({
            type: currentEditionChartType,
            containerSelector: '#chart',
            data,
            colorPalette: [
                '#e6194B', '#3cb44b', '#ffe119', '#4363d8', '#f58231',
                '#911eb4', '#42d4f4', '#f032e6', '#bfef45', '#fabed4',
                '#469990', '#dcbeff', '#9A6324', '#fffac8', '#800000',
                '#aaffc3', '#808000', '#ffd8b1'
            ]
        });
    }

    function fetchDataAndDrawChart(mss) {
        if (!mss) {
            showEmptyGraph('Select manuscripts to render a graph.');
            return;
        }

        showSpinner('Data loading');
        fetch(pageRoot + '/compare_edition_json/?mss=' + encodeURIComponent(mss))
            .then(response => response.json())
            .then(data => {
                originalData = data;
                renderActiveChart(originalData);
            })
            .catch(() => {
                showEmptyGraph('Could not load graph data.');
            });
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
            const background = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
            background.setAttribute('width', clone.getAttribute('width') || svg.clientWidth);
            background.setAttribute('height', clone.getAttribute('height') || svg.clientHeight);
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

    $('#editionChartTypeSelect').select2({
        minimumResultsForSearch: Infinity,
        data: [
            { id: 'parallel', text: 'Parallel Coordinates Plot' },
            { id: 'dot_matrix', text: 'Dot Plot Matrix' },
            { id: 'circos', text: 'Circos Plot' },
            { id: 'sankey', text: 'Sankey Diagram' }
        ]
    });
    $('#editionChartTypeSelect').val(currentEditionChartType).trigger('change');

    $('.manuscript_filter').select2({
        ajax: {
            url: pageRoot + '/manuscripts-autocomplete/',
            dataType: 'json',
            xhrFields: {
                withCredentials: true
            }
        }
    });

    $('#ms_select').on('select2:select select2:unselect', function() {
        const mss = $('#ms_select').select2('data').map(item => window.getManuscriptSelectorValue(item)).filter(Boolean).join(';');
        fetchDataAndDrawChart(mss);
    });

    $('#editionChartTypeSelect').on('change', function() {
        currentEditionChartType = $(this).val() || 'parallel';
        if (originalData.length) {
            renderActiveChart(originalData);
        }
    });

    window.exportEditionSvg = function() {
        if (!lastEditionData.length) {
            alert('No data to export');
            return;
        }
        const svg = getCurrentChartSvgClone();
        if (!svg) {
            alert('No graph to export');
            return;
        }
        const svgString = new XMLSerializer().serializeToString(svg);
        downloadBlob(new Blob([svgString], { type: 'image/svg+xml' }), 'edition_graph.svg');
    };

    window.exportEditionPng = function() {
        if (!lastEditionData.length) {
            alert('No data to export');
            return;
        }
        const svg = getCurrentChartSvgClone();
        if (!svg) {
            alert('No graph to export');
            return;
        }
        const svgString = new XMLSerializer().serializeToString(svg);
        const svgWidth = parseInt(svg.getAttribute('width'), 10);
        const svgHeight = parseInt(svg.getAttribute('height'), 10);
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
            link.download = 'edition_graph.png';
            link.href = canvas.toDataURL('image/png');
            link.click();
        };
        image.src = url;
    };

    window.exportEditionJson = function() {
        if (!lastEditionData.length) {
            alert('No data to export');
            return;
        }
        downloadBlob(
            new Blob([JSON.stringify(lastEditionData, null, 2)], { type: 'application/json' }),
            'edition_data.json'
        );
    };

    window.exportEditionCsv = function() {
        if (!lastEditionData.length) {
            alert('No data to export');
            return;
        }
        const keys = Object.keys(lastEditionData[0]);
        const rows = [
            keys.join(','),
            ...lastEditionData.map(row => keys.map(key => JSON.stringify(row[key] ?? '')).join(','))
        ];
        downloadBlob(new Blob([rows.join('\n')], { type: 'text/csv' }), 'edition_data.csv');
    };
};
