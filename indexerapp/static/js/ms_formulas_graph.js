const colorPalette = [
    '#e6194B', '#3cb44b', '#ffe119', '#4363d8', '#f58231',
    '#911eb4', '#42d4f4', '#f032e6', '#bfef45', '#fabed4',
    '#469990', '#dcbeff', '#9A6324', '#fffac8', '#800000',
    '#aaffc3', '#808000', '#ffd8b1'
];
let traditionColors = {
    'Multiple': '#000075',
    'Unattributed': '#a9a9a9'
};
let traditionMap = {}; // Store id-to-text mapping for traditions

ms_formulas_graph_init = function() {
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

    let originalData = [];

    $('#genreSelect').on('select2:select', function(e) {
        const genreId = e.params.data.id;
        $('#traditionFilter').val(null).trigger('change');
        $('#traditionFilter').select2({
            ajax: {
                url: pageRoot + '/traditions-autocomplete/?genre=' + genreId,
                dataType: 'json',
                xhrFields: {
                    withCredentials: true
                },
                processResults: function(data) {
                    console.log('Tradition filter data:', data.results);
                    // Update traditionColors and traditionMap
                    traditionMap = {};
                    data.results.forEach((trad, index) => {
                        traditionMap[trad.id] = trad.text;
                        if (!traditionColors[trad.text]) {
                            traditionColors[trad.text] = colorPalette[index % colorPalette.length];
                        }
                    });
                    // Add Unattributed to the filter options
                    traditionMap['Unattributed'] = 'Unattributed';
                    data.results.push({ id: 'Unattributed', text: 'Unattributed' });
                    return {
                        results: data.results,
                        pagination: data.pagination
                    };
                }
            }
        });
    });

    $('#identifyTraditionsBtn').on('click', function() {
        console.log('Identify Traditions clicked, originalData:', originalData);
        showStats(originalData);
        renderFilteredChart();
    });

    function setTableHeight() {
        var windowHeight = $(window).height();
        var windowWidth = $(window).width();
        let tableHeight;
        if (windowWidth > 640) {
            tableHeight = windowHeight - 400;
        } else {
            tableHeight = windowHeight - 370;
        }
        $('#chart').css('height', tableHeight + 'px');
    }
    setTableHeight();
    $(window).resize(setTableHeight);

    let left_id = -1;
    let right_id = -1;

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

    $('.manuscript_filter_left').on('select2:select', function(e) {
        left_id = e.params.data.id;
        console.log('Left manuscript selected:', left_id);
        fetchDataAndDrawChart(left_id, right_id);
    });

    $('.manuscript_filter_right').on('select2:select', function(e) {
        right_id = e.params.data.id;
        console.log('Right manuscript selected:', right_id);
        fetchDataAndDrawChart(left_id, right_id);
    });

    $('#traditionFilter').on('change', function() {
        console.log('Tradition filter changed:', $('#traditionFilter').val());
        renderFilteredChart();
    });

    $('#colorizeTraditions').on('change', function() {
        console.log('Colorize traditions toggled:', $('#colorizeTraditions').is(':checked'));
        renderFilteredChart();
    });

    function renderFilteredChart() {
        showSpinner("Updating graph...");
        const selectedIds = $('#traditionFilter').val() || [];
        const selected = selectedIds.map(id => traditionMap[id] || id); // Map IDs to text
        console.log('Selected tradition texts:', selected);
        console.log('Original data:', originalData);
        let filteredData = originalData;

        if (selected.length > 0) {
            filteredData = originalData.filter(item => {
                const traditions = item.formula_traditions || [];
                console.log('Filtering item:', item.formula_id, 'Traditions:', traditions);
                if (selected.includes('Unattributed') && selected.length === 1) {
                    return traditions.length === 0;
                } else if (selected.includes('Unattributed')) {
                    return traditions.length === 0 || selected.some(t => t !== 'Unattributed' && traditions.includes(t));
                } else {
                    return selected.some(t => traditions.includes(t));
                }
            });
        }
        console.log('Filtered data:', filteredData);
        createChart(filteredData);
    }

    function showSpinner(text) {
        $('#chart').html(`<div class="text-center py-10 text-gray-600 font-semibold">${text}...</div>`);
    }

    function fetchDataAndDrawChart(left_id, right_id) {
        if (left_id === -1 || right_id === -1) {
            console.log('Invalid manuscript IDs:', left_id, right_id);
            return;
        }

        showSpinner("Data loading");

        fetch(pageRoot + "/compare_formulas_json/?left=" + left_id + "&right=" + right_id)
            .then(response => response.json())
            .then(data => {
                console.log('Fetched data:', data);
                originalData = data;
                // Assign colors to all traditions in data
                const allTraditions = new Set();
                data.forEach(item => {
                    (item.formula_traditions || []).forEach(trad => allTraditions.add(trad));
                });
                console.log('All traditions in data:', allTraditions);
                let colorIndex = 0;
                allTraditions.forEach(trad => {
                    if (!traditionColors[trad]) {
                        traditionColors[trad] = colorPalette[colorIndex % colorPalette.length];
                        colorIndex++;
                    }
                });
                showStats(originalData);
                showSpinner("Generating graph");
                renderFilteredChart();
            })
            .catch(error => {
                console.error('Fetch error:', error);
            });
    }

    function getWidth() {
        return Math.max(
            document.body.scrollWidth,
            document.documentElement.scrollWidth,
            document.body.offsetWidth,
            document.documentElement.offsetWidth,
            document.documentElement.clientWidth
        );
    }

    function getHeight() {
        return Math.max(
            document.body.scrollHeight,
            document.documentElement.scrollHeight,
            document.body.offsetHeight,
            document.documentElement.offsetHeight,
            document.documentElement.clientHeight
        );
    }

    function showStats(data) {
        console.log('showStats called with data:', data);
        console.log('Current traditionColors:', traditionColors);
        const container = document.getElementById('ms_stats');
        container.innerHTML = '';

        const msGroups = {};
        const allFormulaIds = new Map();
        const allFormulaTraditions = new Map();
        const allTraditions = new Set();

        for (const item of data) {
            const table = item.Table;
            if (!msGroups[table]) msGroups[table] = [];
            msGroups[table].push(item);

            if (!allFormulaIds.has(item.formula_id)) {
                allFormulaIds.set(item.formula_id, new Set());
            }
            allFormulaIds.get(item.formula_id).add(table);

            if (!allFormulaTraditions.has(item.formula_id)) {
                allFormulaTraditions.set(item.formula_id, new Set());
            }
            item.formula_traditions.forEach(trad => {
                allFormulaTraditions.get(item.formula_id).add(trad);
                allTraditions.add(trad);
            });
        }

        const msStats = [];
        const traditionCounts = {};

        allTraditions.forEach(trad => {
            traditionCounts[trad] = { only: 0, count: 0 };
        });
        traditionCounts['Multiple'] = { only: 0, count: 0 };
        traditionCounts['Unattributed'] = { only: 0, count: 0 };

        for (const [ms, entries] of Object.entries(msGroups)) {
            let total = entries.length;
            let unattributed = 0;
            let stats = { ms, total, unattributed };

            for (const trad of allTraditions) {
                stats[trad] = 0;
                stats[`${trad}_only`] = 0;
            }
            stats['Multiple'] = 0;

            for (const e of entries) {
                const t = new Set(e.formula_traditions);
                if (t.size === 0) {
                    unattributed++;
                    traditionCounts['Unattributed'].count++;
                } else if (t.size > 1) {
                    stats['Multiple']++;
                    traditionCounts['Multiple'].count++;
                } else {
                    const trad = Array.from(t)[0];
                    stats[trad]++;
                    traditionCounts[trad].count++;
                    stats[`${trad}_only`]++;
                    traditionCounts[trad].only++;
                }
            }

            msStats.push(stats);
        }

        let inBothMS = 0;
        let totalShared = 0;
        let sharedStats = {};

        allTraditions.forEach(trad => {
            sharedStats[trad] = 0;
        });
        sharedStats['Multiple'] = 0;
        sharedStats['Unattributed'] = 0;

        for (const [id, sets] of allFormulaIds.entries()) {
            if (sets.size > 1) {
                inBothMS++;
                totalShared++;
                const traditions = allFormulaTraditions.get(id);
                if (traditions.size === 0) {
                    sharedStats['Unattributed']++;
                } else if (traditions.size > 1) {
                    sharedStats['Multiple']++;
                } else {
                    sharedStats[Array.from(traditions)[0]]++;
                }
            }
        }

        let html = `<div class="space-y-6">`;

        for (const stat of msStats) {
            html += `
                <div class="border border-gray-300 rounded-lg p-4 bg-white shadow-md">
                    <h3 class="text-lg font-semibold text-gray-800 mb-2">${stat.ms}</h3>
                    <ul class="text-sm text-gray-700 space-y-1">
                        <li><span class="font-medium">Total orations:</span> ${stat.total}</li>`;
            allTraditions.forEach(trad => {
                if (stat[trad] > 0) {
                    const tradColor = traditionColors[trad] || colorPalette[Math.floor(Math.random() * colorPalette.length)];
                    console.log(`Assigning color to ${trad}: ${tradColor}`);
                    html += `<li><span class="dot" style="background-color: ${tradColor};"></span><span class="font-medium">${trad}:</span> ${stat[trad]}</li>`;
                }
            });
            if (stat['Multiple'] > 0) {
                html += `<li><span class="dot" style="background-color: ${traditionColors['Multiple']};"></span><span class="font-medium">Multiple traditions:</span> ${stat['Multiple']}</li>`;
            }
            html += `<li><span class="dot" style="background-color: ${traditionColors['Unattributed']};"></span><span class="font-medium">Unattributed:</span> ${stat.unattributed}</li>
                    </ul>
                </div>`;
        }

        html += `
            <div class="border border-gray-300 rounded-lg p-4 bg-yellow-50 shadow-inner">
                <h3 class="text-lg font-semibold text-yellow-900 mb-2">Global Stats</h3>
                <ul class="text-sm text-yellow-800 space-y-1">
                    <li><span class="font-medium">Number of connections between manuscripts:</span> ${totalShared}</li>`;
        allTraditions.forEach(trad => {
            if (sharedStats[trad] > 0) {
                const tradColor = traditionColors[trad] || colorPalette[Math.floor(Math.random() * colorPalette.length)];
                console.log(`Assigning color to ${trad} (global): ${tradColor}`);
                html += `<li><span class="dot" style="background-color: ${tradColor};"></span><span class="font-medium">${trad}:</span> ${sharedStats[trad]}</li>`;
            }
        });
        if (sharedStats['Multiple'] > 0) {
            html += `<li><span class="dot" style="background-color: ${traditionColors['Multiple']};"></span><span class="font-medium">Multiple traditions:</span> ${sharedStats['Multiple']}</li>`;
        }
        html += `<li><span class="dot" style="background-color: ${traditionColors['Unattributed']};"></span><span class="font-medium">Unattributed:</span> ${sharedStats['Unattributed']}</li>
                </ul>
            </div>
        </div>`;

        container.innerHTML = html;
    }

    function createChart(data) {
        console.log('createChart called with data:', data);
        console.log('traditionColors:', traditionColors);
        let chartHeight = $('#chart').height();
        const margin = {
                top: 20,
                right: 30,
                bottom: 40,
                left: 300
            },
            width = getWidth() - margin.left - margin.right - 50 - 340,
            height = chartHeight - margin.top - margin.bottom;

        $("#chart").empty();

        const svg = d3.select("#chart").append("svg")
            .attr("width", width + margin.left + margin.right)
            .attr("height", height + margin.top + margin.bottom);

        const g = svg.append("g")
            .attr("transform", `translate(${margin.left},${margin.top})`);

        const x = d3.scaleLinear().range([0, width]);
        const y = d3.scalePoint().range([0, height]).padding(0.1);

        const editionIndexes = [...new Set(data.map(d => d.formula_id))];
        console.log('editionIndexes:', editionIndexes);
        y.domain(data.map(d => d.Table));
        x.domain(d3.extent(data, d => d.sequence_in_ms));

        console.log('y.domain:', y.domain());
        console.log('x.domain:', x.domain());

        const colorizeTraditions = $('#colorizeTraditions').is(':checked');

        const color = d3.scaleOrdinal(d3.schemeCategory10).domain(editionIndexes);

        const tooltip = d3.select("body").append("div")
            .attr("class", "tooltip")
            .style("opacity", 0);

        let selectedLine = null;
        let selectedCircles = null;

        function highlightConnection(formula_id) {
            selectedLine = null;
            g.selectAll(".selected-circle").classed("selected-circle", false);

            selectedLine = g.selectAll('path.connection-line')
                .filter(d => d.formula_id === formula_id)
                .classed("selected-line", true)
                .raise();

            selectedCircles = g.selectAll('circle')
                .filter(d => d.formula_id === formula_id)
                .classed("selected-circle", true)
                .raise();
        }

        function handleClickOnCircle(d) {
            highlightConnection(d.formula_id);
        }

        function handleClickOnLine(d) {
            highlightConnection(d.formula_id);
        }

        const groupedData = d3.group(data, d => d.formula_id, d => d.Table);
        console.log('groupedData:', groupedData);

        editionIndexes.forEach(formula_id => {
            const values = data.filter(d => d.formula_id === formula_id);

            let traditionClass = "";
            let connectionColor = color(formula_id);
            let circleColor = color(formula_id);

            if (colorizeTraditions) {
                const traditions = values[0].formula_traditions || [];
                if (traditions.length === 0) {
                    traditionClass = "Unattributed";
                    connectionColor = traditionColors["Unattributed"];
                    circleColor = traditionColors["Unattributed"];
                } else if (traditions.length > 1) {
                    traditionClass = "Multiple";
                    connectionColor = traditionColors["Multiple"];
                    circleColor = traditionColors["Multiple"];
                } else {
                    traditionClass = traditions[0];
                    connectionColor = traditionColors[traditions[0]] || color(formula_id);
                    circleColor = traditionColors[traditions[0]] || color(formula_id);
                }
            }

            g.selectAll(`.connection-line-${formula_id}`)
                .data(data.filter(d => d.formula_id === formula_id))
                .enter()
                .append("path")
                .attr("class", `connection-line connection-line-${formula_id}`)
                .attr("fill", "none")
                .attr("stroke", connectionColor)
                .attr("stroke-width", 3)
                .attr("d", function(d) {
                    const leftMs = d.Table;

                    if (!groupedData.has(formula_id)) return null;

                    const msKeys = Array.from(groupedData.get(formula_id).keys());
                    if (msKeys.length < 2) return null;

                    const rightMs = msKeys.find(key => key !== leftMs);
                    if (!rightMs) return null;

                    const leftEntries = groupedData.get(formula_id).get(leftMs);
                    const rightEntries = groupedData.get(formula_id).get(rightMs);

                    if (!leftEntries || !rightEntries) return null;
                    const leftCount = leftEntries.length;
                    const rightCount = rightEntries.length;

                    let connections = [];

                    for (let i = 0; i < Math.max(leftCount, rightCount); i++) {
                        let source = leftEntries[Math.min(i, leftCount - 1)];
                        let target = rightEntries[Math.min(i, rightCount - 1)];

                        connections.push({
                            source: source,
                            target: target
                        });
                    }

                    let pathString = "";
                    connections.forEach(connection => {
                        if (connection.source.Table !== connection.target.Table) {
                            pathString += `M${x(connection.source.sequence_in_ms)} ${y(connection.source.Table)} L${x(connection.target.sequence_in_ms)} ${y(connection.target.Table)}`;
                        }
                    });
                    return pathString;
                })
                .on("mouseover", function(event, d) {
                    tooltip.transition()
                        .duration(200)
                        .style("opacity", .9);
                    tooltip.html(`Formula: ${values[0].formula}<br>
                                  Tradition: ${values[0].formula_traditions.join(', ')}<br>
                                  Sequence: ${values[0].sequence_in_ms} -> ${values[values.length - 1].sequence_in_ms}`)
                        .style("left", `${event.pageX + 5}px`)
                        .style("top", `${event.pageY - 28}px`);
                })
                .on("mouseout", function() {
                    tooltip.transition()
                        .duration(500)
                        .style("opacity", 0);
                })
                .on("click", function(event, d) {
                    handleClickOnLine.call(this, d);
                    event.stopPropagation();
                });

            g.selectAll("dot")
                .data(values)
                .enter().append("circle")
                .attr("r", 7)
                .attr("cx", d => x(d.sequence_in_ms))
                .attr("cy", d => y(d.Table))
                .attr("fill", circleColor)
                .on("mouseover", function(event, d) {
                    tooltip.transition()
                        .duration(200)
                        .style("opacity", .9);
                    tooltip.html(`Formula: ${d.formula_id}<br>
                        Tradition: ${values[0].formula_traditions.join(', ')}<br>
                        Sequence: ${d.sequence_in_ms}<br>${d.rubric_name}<br>${d.formula}`)
                        .style("left", `${event.pageX + 5}px`)
                        .style("top", `${event.pageY - 28}px`);
                })
                .on("mouseout", function() {
                    tooltip.transition()
                        .duration(500)
                        .style("opacity", 0);
                })
                .on("click", function(event, d) {
                    handleClickOnCircle.call(this, d);
                    event.stopPropagation();
                });
        });

        g.append("g").attr("class", "y axis")
            .attr("transform", `translate(-5,0)`)
            .call(d3.axisLeft(y)
                .tickFormat(d => {
                    const maxLength = 90;
                    let text = d;
                    if (text.length > maxLength) {
                        text = text.substring(0, maxLength) + "...";
                    }
                    return text;
                }))
            .selectAll("text")
            .call(wrap, margin.left - 10);

        g.append("g").attr("class", "x axis")
            .attr("transform", `translate(0,${height})`)
            .call(d3.axisBottom(x));

        svg.on("click", function(event) {
            if (!d3.select(event.target).classed("dot") && !d3.select(event.target).classed("connection-line")) {
                g.selectAll(".selected-line").classed("selected-line", false);
                g.selectAll(".selected-circle").classed("selected-circle", false);
            }
        });

        function handleZoom(e) {
            const new_x = e.transform.rescaleX(x);

            g.select(".x.axis").call(d3.axisBottom(new_x));

            g.selectAll('circle')
                .attr('cx', d => new_x(d.sequence_in_ms));

            g.selectAll('path.connection-line')
                .attr('d', function(d) {
                    const leftMs = d.Table;

                    if (!groupedData.has(d.formula_id)) return null;

                    const msKeys = Array.from(groupedData.get(d.formula_id).keys());
                    if (msKeys.length < 2) return null;

                    const rightMs = msKeys.find(key => key !== leftMs);
                    if (!rightMs) return null;

                    const leftEntries = groupedData.get(d.formula_id).get(leftMs);
                    const rightEntries = groupedData.get(d.formula_id).get(rightMs);

                    if (!leftEntries || !rightEntries) return null;
                    const leftCount = leftEntries.length;
                    const rightCount = rightEntries.length;

                    let connections = [];

                    for (let i = 0; i < Math.max(leftCount, rightCount); i++) {
                        let source = leftEntries[Math.min(i, leftCount - 1)];
                        let target = rightEntries[Math.min(i, rightCount - 1)];

                        connections.push({
                            source: source,
                            target: target
                        });
                    }
                    let pathString = "";
                    connections.forEach(connection => {
                        if (connection.source.Table !== connection.target.Table) {
                            pathString += `M${new_x(connection.source.sequence_in_ms)} ${y(connection.source.Table)} L${new_x(connection.target.sequence_in_ms)} ${y(connection.target.Table)}`;
                        }
                    });
                    return pathString;
                });
        }

        let zoom = d3.zoom()
            .on('zoom', handleZoom);

        svg.call(zoom);
    }
}

function wrap(text, width) {
    text.each(function() {
        var text = d3.select(this),
            words = text.text().split(/\s+/).reverse(),
            word,
            line = [],
            lineNumber = 0,
            lineHeight = 1.1,
            y = text.attr("y"),
            dy = parseFloat(text.attr("dy")),
            tspan = text.text(null).append("tspan").attr("x", -3).attr("y", y).attr("dy", dy + "em");
        while (word = words.pop()) {
            line.push(word);
            tspan.text(line.join(" "));
            if (tspan.node().getComputedTextLength() > width) {
                line.pop();
                tspan.text(line.join(" "));
                line = [word];
                tspan = text.append("tspan").attr("x", -3).attr("y", y).attr("dy", ++lineNumber * lineHeight + dy + "em").text(word);
            }
        }
    });
}