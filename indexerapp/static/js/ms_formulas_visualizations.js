(function() {
    const LOCAL_CHART_MIN_WIDTH = 720;
    const LOCAL_CHART_STEP_WIDTH = 28;

    function ensureTooltip() {
        let tooltip = d3.select('#formulas-chart-tooltip');
        if (tooltip.empty()) {
            tooltip = d3.select('body')
                .append('div')
                .attr('id', 'formulas-chart-tooltip')
                .attr('class', 'tooltip')
                .style('opacity', 0)
                .style('pointer-events', 'none');
        }
        return tooltip;
    }

    function truncateLabel(text, maxLength = 90) {
        if (!text) {
            return '';
        }
        return text.length > maxLength ? `${text.substring(0, maxLength)}...` : text;
    }

    function getPrayerText(item) {
        return item?.formula_text || item?.formula_text_from_ms || item?.formula || item?.rubric_name || 'No prayer text available.';
    }

    function formatPrayerTooltip(item) {
        return `Prayer: ${truncateLabel(getPrayerText(item), 320)}`;
    }

    function collectPrayerTexts(items, limit = 3) {
        return [...new Set((items || []).map(getPrayerText).filter(Boolean))].slice(0, limit);
    }

    function formatPrayerListTooltip(items) {
        const prayers = collectPrayerTexts(items);
        if (!prayers.length) {
            return formatPrayerTooltip(null);
        }
        return prayers.map((prayer, index) => `Prayer ${index + 1}: ${truncateLabel(prayer, 220)}`).join('<br>');
    }

    function wrapAxisText(text, width) {
        text.each(function() {
            const currentText = d3.select(this);
            const words = currentText.text().split(/\s+/).reverse();
            const y = currentText.attr('y');
            const dy = parseFloat(currentText.attr('dy')) || 0;
            let word;
            let line = [];
            let lineNumber = 0;
            const lineHeight = 1.1;
            let tspan = currentText.text(null)
                .append('tspan')
                .attr('x', -3)
                .attr('y', y)
                .attr('dy', `${dy}em`);

            while ((word = words.pop())) {
                line.push(word);
                tspan.text(line.join(' '));
                if (tspan.node().getComputedTextLength() > width) {
                    line.pop();
                    tspan.text(line.join(' '));
                    line = [word];
                    tspan = currentText.append('tspan')
                        .attr('x', -3)
                        .attr('y', y)
                        .attr('dy', `${++lineNumber * lineHeight + dy}em`)
                        .text(word);
                }
            }
        });
    }

    function applyTextOutline(selection, strokeWidth = 3) {
        selection
            .attr('stroke', 'white')
            .attr('stroke-width', strokeWidth)
            .attr('paint-order', 'stroke fill')
            .attr('stroke-linejoin', 'round');
    }

    function splitTextIntoLines(text, maxChars = 18) {
        if (!text) {
            return [''];
        }

        const words = text.split(/\s+/).filter(Boolean);
        const lines = [];
        let currentLine = '';

        words.forEach(word => {
            const candidate = currentLine ? `${currentLine} ${word}` : word;
            if (candidate.length <= maxChars || !currentLine) {
                currentLine = candidate;
            } else {
                lines.push(currentLine);
                currentLine = word;
            }
        });

        if (currentLine) {
            lines.push(currentLine);
        }

        return lines.length ? lines : [text];
    }

    function appendMultilineText(selection, lines, lineHeight = 1.1) {
        selection.text(null);
        lines.forEach((line, index) => {
            selection.append('tspan')
                .attr('x', selection.attr('x'))
                .attr('dy', index === 0 ? '0em' : `${lineHeight}em`)
                .text(line);
        });
    }

    function clearContainer(containerSelector) {
        d3.select(containerSelector).selectAll('*').remove();
    }

    function showEmptyState(containerSelector, message) {
        clearContainer(containerSelector);
        d3.select(containerSelector)
            .append('div')
            .attr('class', 'text-center py-10 text-gray-600 font-semibold')
            .text(message);
    }

    function getContainerDimensions(containerSelector, data, valueAccessor, margin) {
        const chartElement = document.querySelector(containerSelector);
        const bounds = chartElement?.getBoundingClientRect();
        const containerWidth = Math.max(bounds?.width || 0, LOCAL_CHART_MIN_WIDTH + margin.left + margin.right);
        const chartHeight = Math.max(chartElement?.clientHeight || 0, 420);
        const uniquePositions = new Set(data.map(valueAccessor)).size || 1;
        const preferredWidth = Math.max(LOCAL_CHART_MIN_WIDTH, uniquePositions * LOCAL_CHART_STEP_WIDTH);
        const width = Math.max(LOCAL_CHART_MIN_WIDTH, Math.min(preferredWidth, containerWidth - margin.left - margin.right));
        const height = Math.max(320, chartHeight - margin.top - margin.bottom);

        return { width, height };
    }

    function buildFormulaGroups(data) {
        return Array.from(d3.group(data, item => item.formula_id), ([formulaId, items]) => ({
            formulaId,
            items
        }));
    }

    function getFormulaColorResolver(formulaGroups, colorPalette, colorizeTraditions, traditionColors) {
        const fallbackScale = d3.scaleOrdinal(colorPalette).domain(formulaGroups.map(group => group.formulaId));
        return function resolveColor(group) {
            if (!colorizeTraditions) {
                return fallbackScale(group.formulaId);
            }

            const traditions = group.items[0]?.formula_traditions || [];
            if (traditions.length === 0) {
                return traditionColors.Unattributed;
            }
            if (traditions.length > 1) {
                return traditionColors.Multiple;
            }
            return traditionColors[traditions[0]] || fallbackScale(group.formulaId);
        };
    }

    function getManuscriptColorScale(data, colorPalette) {
        return d3.scaleOrdinal(colorPalette).domain([...new Set(data.map(item => item.Table))]);
    }

    function polarToCartesian(angle, radius) {
        return [Math.cos(angle) * radius, Math.sin(angle) * radius];
    }

    function distributeNodesVertically(nodes, extentHeight, gap = 14) {
        if (!nodes.length) {
            return;
        }

        const sortedNodes = nodes.slice().sort((left, right) => left.y0 - right.y0);
        const totalNodeHeight = sortedNodes.reduce((sum, node) => sum + (node.y1 - node.y0), 0);
        const availableGap = Math.max(6, (extentHeight - totalNodeHeight) / Math.max(1, sortedNodes.length - 1));
        const appliedGap = Math.min(gap, availableGap);
        const blockHeight = totalNodeHeight + appliedGap * Math.max(0, sortedNodes.length - 1);
        let currentY = Math.max(0, (extentHeight - blockHeight) / 2);

        sortedNodes.forEach(node => {
            const nodeHeight = node.y1 - node.y0;
            node.y0 = currentY;
            node.y1 = node.y0 + nodeHeight;
            currentY = node.y1 + appliedGap;
        });

        const overflow = currentY - appliedGap - extentHeight;
        if (overflow > 0) {
            sortedNodes.forEach(node => {
                node.y0 -= overflow;
                node.y1 -= overflow;
            });
        }
    }

    function renderParallelCoordinates(options) {
        const { containerSelector, data, colorPalette, traditionColors, colorizeTraditions } = options;
        if (!data.length) {
            showEmptyState(containerSelector, 'No data available for the selected filters.');
            return;
        }

        clearContainer(containerSelector);

        const tooltip = ensureTooltip();
        const margin = { top: 20, right: 30, bottom: 40, left: 300 };
        const { width, height } = getContainerDimensions(containerSelector, data, item => item.sequence_in_ms, margin);
        const svg = d3.select(containerSelector)
            .append('svg')
            .attr('width', width + margin.left + margin.right)
            .attr('height', height + margin.top + margin.bottom);

        const chart = svg.append('g')
            .attr('transform', `translate(${margin.left},${margin.top})`);

        const x = d3.scaleLinear()
            .range([0, width])
            .domain(d3.extent(data, item => item.sequence_in_ms));

        const manuscripts = [...new Set(data.map(item => item.Table))];
        const y = d3.scalePoint()
            .range([0, height])
            .padding(0.12)
            .domain(manuscripts);

        const formulaGroups = buildFormulaGroups(data);
        const legacyScale = d3.scaleOrdinal(d3.schemeCategory10).domain(formulaGroups.map(group => group.formulaId));
        const resolveColor = function(group) {
            if (!colorizeTraditions) {
                return legacyScale(group.formulaId);
            }

            const traditions = group.items[0]?.formula_traditions || [];
            if (traditions.length === 0) {
                return traditionColors.Unattributed;
            }
            if (traditions.length > 1) {
                return traditionColors.Multiple;
            }
            return traditionColors[traditions[0]] || legacyScale(group.formulaId);
        };
        const groupedData = d3.group(data, item => item.formula_id, item => item.Table);

        function buildConnections(formulaId, xScale) {
            if (!groupedData.has(formulaId)) {
                return [];
            }

            const manuscriptMap = groupedData.get(formulaId);
            const keys = Array.from(manuscriptMap.keys());
            if (keys.length < 2) {
                return [];
            }

            const leftKey = keys[0];
            const rightKey = keys[1];
            const leftEntries = manuscriptMap.get(leftKey) || [];
            const rightEntries = manuscriptMap.get(rightKey) || [];
            const steps = Math.max(leftEntries.length, rightEntries.length);
            const segments = [];

            for (let index = 0; index < steps; index++) {
                const source = leftEntries[Math.min(index, leftEntries.length - 1)];
                const target = rightEntries[Math.min(index, rightEntries.length - 1)];
                if (!source || !target || source.Table === target.Table) {
                    continue;
                }

                segments.push({
                    formulaId,
                    source,
                    target,
                    path: `M${xScale(source.sequence_in_ms)} ${y(source.Table)} L${xScale(target.sequence_in_ms)} ${y(target.Table)}`
                });
            }

            return segments;
        }

        const lineLayer = chart.append('g').attr('class', 'parallel-lines');
        const pointLayer = chart.append('g').attr('class', 'parallel-points');

        let selectedFormulaId = null;

        function highlightFormula(formulaId) {
            selectedFormulaId = formulaId;
            lineLayer.selectAll('path.connection-line')
                .classed('selected-line', segment => segment.formulaId === formulaId);
            pointLayer.selectAll('circle.parallel-point')
                .classed('selected-circle', point => point.formula_id === formulaId);
        }

        function renderParallelMarks(xScale) {
            lineLayer.selectAll('*').remove();
            pointLayer.selectAll('*').remove();

            formulaGroups.forEach(group => {
                const color = resolveColor(group);
                const segments = buildConnections(group.formulaId, xScale);

                lineLayer.selectAll(null)
                    .data(segments)
                    .enter()
                    .append('path')
                    .attr('class', 'connection-line')
                    .attr('fill', 'none')
                    .attr('stroke', color)
                    .attr('stroke-width', 3)
                    .attr('d', segment => segment.path)
                    .on('mouseover', function(event) {
                        const first = group.items[0];
                        const last = group.items[group.items.length - 1];
                        tooltip.transition().duration(150).style('opacity', 0.95);
                        tooltip.html(`Formula: ${first.formula}<br>Tradition: ${(first.formula_traditions || []).join(', ') || 'Unattributed'}<br>Sequence: ${first.sequence_in_ms} -> ${last.sequence_in_ms}<br>${formatPrayerTooltip(first)}`)
                            .style('left', `${event.pageX + 5}px`)
                            .style('top', `${event.pageY - 28}px`);
                    })
                    .on('mouseout', function() {
                        tooltip.transition().duration(250).style('opacity', 0);
                    })
                    .on('click', function(event) {
                        highlightFormula(group.formulaId);
                        event.stopPropagation();
                    });

                pointLayer.selectAll(null)
                    .data(group.items)
                    .enter()
                    .append('circle')
                    .attr('class', 'parallel-point')
                    .attr('r', 7)
                    .attr('cx', item => xScale(item.sequence_in_ms))
                    .attr('cy', item => y(item.Table))
                    .attr('fill', color)
                    .on('mouseover', function(event, item) {
                        tooltip.transition().duration(150).style('opacity', 0.95);
                        tooltip.html(`Formula: ${item.formula_id}<br>Tradition: ${(group.items[0].formula_traditions || []).join(', ') || 'Unattributed'}<br>Sequence: ${item.sequence_in_ms}<br>${item.rubric_name}<br>${formatPrayerTooltip(item)}`)
                            .style('left', `${event.pageX + 5}px`)
                            .style('top', `${event.pageY - 28}px`);
                    })
                    .on('mouseout', function() {
                        tooltip.transition().duration(250).style('opacity', 0);
                    })
                    .on('click', function(event) {
                        highlightFormula(group.formulaId);
                        event.stopPropagation();
                    });
            });

            if (selectedFormulaId) {
                highlightFormula(selectedFormulaId);
            }
        }

        renderParallelMarks(x);

        chart.append('g')
            .attr('class', 'y axis')
            .attr('transform', 'translate(-5,0)')
            .call(d3.axisLeft(y).tickFormat(label => truncateLabel(label)))
            .selectAll('text')
            .call(wrapAxisText, margin.left - 10)
            .call(applyTextOutline, 4);

        chart.append('g')
            .attr('class', 'x axis')
            .attr('transform', `translate(0,${height})`)
            .call(d3.axisBottom(x));

        svg.on('click', function(event) {
            if (!d3.select(event.target).classed('parallel-point') && !d3.select(event.target).classed('connection-line')) {
                selectedFormulaId = null;
                chart.selectAll('.selected-line').classed('selected-line', false);
                chart.selectAll('.selected-circle').classed('selected-circle', false);
            }
        });

        svg.call(
            d3.zoom().on('zoom', function(event) {
                const newX = event.transform.rescaleX(x);
                chart.select('.x.axis').call(d3.axisBottom(newX));
                renderParallelMarks(newX);
            })
        );
    }

    function renderDotPlotMatrix(options) {
        const { containerSelector, data, colorPalette, traditionColors, colorizeTraditions } = options;
        if (!data.length) {
            showEmptyState(containerSelector, 'No data available for the selected filters.');
            return;
        }

        const manuscripts = [...new Set(data.map(item => item.Table))];
        if (manuscripts.length < 2) {
            showEmptyState(containerSelector, 'Dot Plot Matrix needs data from two manuscripts.');
            return;
        }

        clearContainer(containerSelector);

        const tooltip = ensureTooltip();
        const margin = { top: 30, right: 30, bottom: 70, left: 90 };
        const leftManuscript = manuscripts[0];
        const rightManuscript = manuscripts[1];

        const formulaGroups = buildFormulaGroups(data);
        const pairData = [];
        formulaGroups.forEach(group => {
            const byManuscript = d3.group(group.items, item => item.Table);
            const leftEntries = (byManuscript.get(leftManuscript) || []).slice().sort((a, b) => a.sequence_in_ms - b.sequence_in_ms);
            const rightEntries = (byManuscript.get(rightManuscript) || []).slice().sort((a, b) => a.sequence_in_ms - b.sequence_in_ms);

            if (!leftEntries.length || !rightEntries.length) {
                return;
            }

            const steps = Math.max(leftEntries.length, rightEntries.length);
            for (let index = 0; index < steps; index++) {
                pairData.push({
                    formulaId: group.formulaId,
                    left: leftEntries[Math.min(index, leftEntries.length - 1)],
                    right: rightEntries[Math.min(index, rightEntries.length - 1)],
                    traditions: group.items[0]?.formula_traditions || []
                });
            }
        });

        if (!pairData.length) {
            showEmptyState(containerSelector, 'No shared formula pairs to plot for the selected manuscripts.');
            return;
        }

        const { width, height } = getContainerDimensions(containerSelector, pairData, item => item.left.sequence_in_ms, margin);
        const svg = d3.select(containerSelector)
            .append('svg')
            .attr('width', width + margin.left + margin.right)
            .attr('height', height + margin.top + margin.bottom);

        const chart = svg.append('g')
            .attr('transform', `translate(${margin.left},${margin.top})`);

        const x = d3.scaleLinear().range([0, width]).domain(d3.extent(pairData, item => item.left.sequence_in_ms));
        const y = d3.scaleLinear().range([height, 0]).domain(d3.extent(pairData, item => item.right.sequence_in_ms));
        const resolveColor = getFormulaColorResolver(formulaGroups, colorPalette, colorizeTraditions, traditionColors);
        const colorByFormula = new Map(formulaGroups.map(group => [String(group.formulaId), resolveColor(group)]));

        chart.append('g')
            .attr('class', 'x axis')
            .attr('transform', `translate(0,${height})`)
            .call(d3.axisBottom(x));

        chart.append('g')
            .attr('class', 'y axis')
            .call(d3.axisLeft(y));

        chart.selectAll('line.matrix-grid-x')
            .data(x.ticks(8))
            .enter()
            .append('line')
            .attr('class', 'matrix-grid')
            .attr('x1', tick => x(tick))
            .attr('x2', tick => x(tick))
            .attr('y1', 0)
            .attr('y2', height)
            .attr('stroke', '#e5e7eb')
            .attr('stroke-width', 1);

        chart.selectAll('line.matrix-grid-y')
            .data(y.ticks(8))
            .enter()
            .append('line')
            .attr('class', 'matrix-grid')
            .attr('x1', 0)
            .attr('x2', width)
            .attr('y1', tick => y(tick))
            .attr('y2', tick => y(tick))
            .attr('stroke', '#e5e7eb')
            .attr('stroke-width', 1);

        chart.selectAll('circle.matrix-point')
            .data(pairData)
            .enter()
            .append('circle')
            .attr('class', 'matrix-point')
            .attr('r', 6)
            .attr('cx', item => x(item.left.sequence_in_ms))
            .attr('cy', item => y(item.right.sequence_in_ms))
            .attr('fill', item => colorByFormula.get(String(item.formulaId)))
            .attr('stroke', 'white')
            .attr('stroke-width', 1.5)
            .on('mouseover', function(event, item) {
                tooltip.transition().duration(150).style('opacity', 0.95);
                tooltip.html(`Formula: ${item.formulaId}<br>${leftManuscript}: ${item.left.sequence_in_ms}<br>${rightManuscript}: ${item.right.sequence_in_ms}<br>Tradition: ${item.traditions.join(', ') || 'Unattributed'}<br>${formatPrayerTooltip(item.left)}`)
                    .style('left', `${event.pageX + 5}px`)
                    .style('top', `${event.pageY - 28}px`);
            })
            .on('mouseout', function() {
                tooltip.transition().duration(250).style('opacity', 0);
            });

        svg.append('text')
            .attr('x', margin.left + width / 2)
            .attr('y', margin.top + height + 48)
            .attr('text-anchor', 'middle')
            .attr('font-size', 12)
            .attr('font-weight', 700)
            .attr('fill', '#111827')
            .text(truncateLabel(leftManuscript, 50));

        svg.append('text')
            .attr('transform', `translate(20, ${margin.top + height / 2}) rotate(-90)`)
            .attr('text-anchor', 'middle')
            .attr('font-size', 12)
            .attr('font-weight', 700)
            .attr('fill', '#111827')
            .text(truncateLabel(rightManuscript, 50));
    }

    function renderCircosPlot(options) {
        const { containerSelector, data, colorPalette, traditionColors, colorizeTraditions } = options;
        if (!data.length) {
            showEmptyState(containerSelector, 'No data available for the selected filters.');
            return;
        }

        clearContainer(containerSelector);

        const tooltip = ensureTooltip();
        const container = document.querySelector(containerSelector);
        const size = Math.max(Math.min(container?.clientWidth || 800, 900), 520);
        const svg = d3.select(containerSelector)
            .append('svg')
            .attr('width', size)
            .attr('height', size);

        const chart = svg.append('g')
            .attr('transform', `translate(${size / 2},${size / 2})`);

        const manuscripts = [...new Set(data.map(item => item.Table))];
        const radius = size * 0.34;
        const outerRadius = radius + 10;
        const manuscriptGroups = manuscripts.map(manuscript => ({
            manuscript,
            values: data.filter(item => item.Table === manuscript)
        }));
        const arcAngle = (Math.PI * 2) / manuscriptGroups.length;
        const formulaGroups = buildFormulaGroups(data);
        const resolveColor = getFormulaColorResolver(formulaGroups, colorPalette, colorizeTraditions, traditionColors);

        manuscriptGroups.forEach((group, index) => {
            group.startAngle = index * arcAngle - Math.PI / 2;
            group.endAngle = group.startAngle + arcAngle * 0.84;
            group.arc = d3.arc()
                .innerRadius(radius)
                .outerRadius(outerRadius)
                .startAngle(group.startAngle)
                .endAngle(group.endAngle);
        });

        chart.selectAll('path.manuscript-arc')
            .data(manuscriptGroups)
            .enter()
            .append('path')
            .attr('class', 'manuscript-arc')
            .attr('d', group => group.arc())
            .attr('fill', 'none')
            .attr('stroke', '#d1d5db')
            .attr('stroke-width', 1)
            .attr('stroke-dasharray', '4 4');

        const labelLayer = chart.append('g').attr('class', 'circos-labels');
        labelLayer.selectAll('text.manuscript-label')
            .data(manuscriptGroups)
            .enter()
            .append('text')
            .attr('class', 'manuscript-label')
            .attr('text-anchor', group => {
                const angle = (group.startAngle + group.endAngle) / 2;
                return Math.cos(angle) >= 0 ? 'start' : 'end';
            })
            .attr('font-size', 13)
            .attr('font-weight', 700)
            .attr('fill', '#111827')
            .attr('transform', group => {
                const angle = (group.startAngle + group.endAngle) / 2;
                const [x, y] = polarToCartesian(angle, outerRadius + 32);
                return `translate(${x},${y})`;
            })
            .each(function(group) {
                const label = d3.select(this)
                    .attr('x', 0)
                    .attr('y', 0);
                appendMultilineText(label, splitTextIntoLines(group.manuscript, 18), 1.05);
                applyTextOutline(label, 4);
            });

        const positions = new Map();
        manuscriptGroups.forEach(group => {
            group.values.forEach((value, index) => {
                const ratio = group.values.length <= 1 ? 0.5 : index / (group.values.length - 1);
                const angle = group.startAngle + (group.endAngle - group.startAngle) * ratio;
                positions.set(`${group.manuscript}::${value.formula_id}::${value.sequence_in_ms}`, { angle, value, manuscript: group.manuscript });
            });
        });

        formulaGroups.forEach(group => {
            const color = resolveColor(group);
            const uniqueManuscripts = [...new Set(group.items.map(item => item.Table))];

            group.items.forEach(item => {
                const key = `${item.Table}::${item.formula_id}::${item.sequence_in_ms}`;
                const point = positions.get(key);
                const [x, y] = polarToCartesian(point.angle, radius - 6);
                chart.append('circle')
                    .attr('cx', x)
                    .attr('cy', y)
                    .attr('r', 4)
                    .attr('fill', color)
                    .attr('stroke', 'white')
                    .attr('stroke-width', 1.5)
                    .on('mouseover', function(event) {
                        tooltip.transition().duration(150).style('opacity', 0.95);
                        tooltip.html(`Formula: ${item.formula_id}<br>Manuscript: ${item.Table}<br>Sequence: ${item.sequence_in_ms}<br>${formatPrayerTooltip(item)}`)
                            .style('left', `${event.pageX + 5}px`)
                            .style('top', `${event.pageY - 28}px`);
                    })
                    .on('mouseout', function() {
                        tooltip.transition().duration(250).style('opacity', 0);
                    });
            });

            if (uniqueManuscripts.length < 2) {
                return;
            }

            for (let index = 0; index < group.items.length - 1; index++) {
                const source = positions.get(`${group.items[index].Table}::${group.items[index].formula_id}::${group.items[index].sequence_in_ms}`);
                const target = positions.get(`${group.items[index + 1].Table}::${group.items[index + 1].formula_id}::${group.items[index + 1].sequence_in_ms}`);
                if (!source || !target || source.manuscript === target.manuscript) {
                    continue;
                }

                const [x1, y1] = polarToCartesian(source.angle, radius - 6);
                const [x2, y2] = polarToCartesian(target.angle, radius - 6);
                const path = d3.path();
                path.moveTo(x1, y1);
                path.quadraticCurveTo(0, 0, x2, y2);

                chart.append('path')
                    .attr('d', path.toString())
                    .attr('fill', 'none')
                    .attr('stroke', color)
                    .attr('stroke-width', 2.5)
                    .attr('stroke-opacity', 0.75)
                    .on('mouseover', function(event) {
                        tooltip.transition().duration(150).style('opacity', 0.95);
                        tooltip.html(`Formula: ${group.formulaId}<br>Tradition: ${(group.items[0].formula_traditions || []).join(', ') || 'Unattributed'}<br>${formatPrayerTooltip(group.items[0])}`)
                            .style('left', `${event.pageX + 5}px`)
                            .style('top', `${event.pageY - 28}px`);
                    })
                    .on('mouseout', function() {
                        tooltip.transition().duration(250).style('opacity', 0);
                    });
            }
        });
    }

    function renderSankeyDiagram(options) {
        const { containerSelector, data, colorPalette, traditionColors, colorizeTraditions } = options;
        if (!data.length) {
            showEmptyState(containerSelector, 'No data available for the selected filters.');
            return;
        }

        if (typeof d3.sankey !== 'function') {
            showEmptyState(containerSelector, 'Sankey renderer is unavailable because d3-sankey is not loaded.');
            return;
        }

        clearContainer(containerSelector);

        const tooltip = ensureTooltip();
        const margin = { top: 20, right: 30, bottom: 20, left: 20 };
        const { width, height } = getContainerDimensions(containerSelector, data, item => item.sequence_in_ms, margin);
        const sankeyHeight = Math.max(height, 520);
        const svg = d3.select(containerSelector)
            .append('svg')
            .attr('width', width + margin.left + margin.right)
            .attr('height', sankeyHeight + margin.top + margin.bottom);

        const chart = svg.append('g')
            .attr('transform', `translate(${margin.left},${margin.top})`);

        const formulaGroups = buildFormulaGroups(data);
        const resolveColor = getFormulaColorResolver(formulaGroups, colorPalette, colorizeTraditions, traditionColors);
        const nodes = [];
        const nodeIndex = new Map();
        const links = new Map();

        function ensureNode(key, node) {
            if (!nodeIndex.has(key)) {
                nodeIndex.set(key, nodes.length);
                nodes.push(node);
            }
            return nodeIndex.get(key);
        }

        data.forEach(item => {
            const manuscriptKey = `ms:${item.Table}`;
            const formulaKey = `formula:${item.formula_id}`;
            const traditions = item.formula_traditions || [];
            const traditionName = traditions.length === 0
                ? 'Unattributed'
                : traditions.length > 1
                    ? 'Multiple'
                    : traditions[0];
            const traditionKey = `trad:${traditionName}`;

            const manuscriptNode = ensureNode(manuscriptKey, { name: item.Table, kind: 'manuscript', items: [] });
            const formulaNode = ensureNode(formulaKey, { name: `Formula ${item.formula_id}`, kind: 'formula', formulaId: item.formula_id, items: [] });
            const traditionNode = ensureNode(traditionKey, { name: traditionName, kind: 'tradition', items: [] });

            nodes[manuscriptNode].items.push(item);
            nodes[formulaNode].items.push(item);
            nodes[traditionNode].items.push(item);

            const leftLinkKey = `${manuscriptNode}->${formulaNode}`;
            const rightLinkKey = `${formulaNode}->${traditionNode}`;

            if (!links.has(leftLinkKey)) {
                links.set(leftLinkKey, { source: manuscriptNode, target: formulaNode, value: 0, colorKey: item.formula_id, items: [] });
            }
            if (!links.has(rightLinkKey)) {
                links.set(rightLinkKey, { source: formulaNode, target: traditionNode, value: 0, traditionName, items: [] });
            }

            links.get(leftLinkKey).value += 1;
            links.get(rightLinkKey).value += 1;
            links.get(leftLinkKey).items.push(item);
            links.get(rightLinkKey).items.push(item);
        });

        const maxColumnNodes = Math.max(
            nodes.filter(node => node.kind === 'manuscript').length,
            nodes.filter(node => node.kind === 'tradition').length,
            1
        );
        const traditionNodeCount = Math.max(1, nodes.filter(node => node.kind === 'tradition').length);
        const desiredTraditionGap = 120;
        const estimatedTraditionNodeHeight = 20;
        const desiredTraditionLayoutHeight = traditionNodeCount * estimatedTraditionNodeHeight
            + Math.max(0, traditionNodeCount - 1) * desiredTraditionGap
            + 80;
        const sankeyLayoutHeight = Math.max(sankeyHeight, desiredTraditionLayoutHeight);
        const dynamicNodePadding = Math.max(18, Math.floor(sankeyLayoutHeight / (traditionNodeCount * 2.8)));

        const sankey = d3.sankey()
            .nodeWidth(18)
            .nodePadding(dynamicNodePadding)
            .nodeAlign(node => {
                if (node.kind === 'manuscript') {
                    return 0;
                }
                if (node.kind === 'formula') {
                    return 1;
                }
                return 2;
            })
            .nodeSort((left, right) => left.name.localeCompare(right.name))
            .extent([[0, 0], [width, sankeyLayoutHeight]]);

        const graph = sankey({
            nodes: nodes.map(node => ({ ...node })),
            links: Array.from(links.values()).map(link => ({ ...link }))
        });

        distributeNodesVertically(graph.nodes.filter(node => node.kind === 'tradition'), sankeyLayoutHeight, desiredTraditionGap);
        sankey.update(graph);

        svg.attr('height', sankeyLayoutHeight + margin.top + margin.bottom);

        const formulaColorScale = d3.scaleOrdinal(colorPalette).domain(formulaGroups.map(group => group.formulaId));

        let activeFormulaNode = null;

        function linkColor(link) {
            if (activeFormulaNode && (link.source.index === activeFormulaNode || link.target.index === activeFormulaNode)) {
                return '#111111';
            }
            if (link.traditionName) {
                return traditionColors[link.traditionName] || '#9ca3af';
            }
            return formulaColorScale(link.colorKey);
        }

        function updateLinkHighlight() {
            chart.selectAll('path.sankey-link')
                .attr('stroke', linkColor)
                .attr('stroke-opacity', link => (activeFormulaNode && (link.source.index === activeFormulaNode || link.target.index === activeFormulaNode)) ? 0.95 : 0.45);
        }

        chart.append('g')
            .selectAll('path')
            .data(graph.links)
            .enter()
            .append('path')
            .attr('class', 'sankey-link')
            .attr('d', d3.sankeyLinkHorizontal())
            .attr('fill', 'none')
            .attr('stroke', linkColor)
            .attr('stroke-opacity', 0.45)
            .attr('stroke-width', link => Math.max(1, link.width))
            .on('mouseover', function(event, link) {
                tooltip.transition().duration(150).style('opacity', 0.95);
                tooltip.html(`${link.source.name} -> ${link.target.name}<br>Weight (number of linked occurrences): ${link.value}<br>${formatPrayerListTooltip(link.items)}`)
                    .style('left', `${event.pageX + 5}px`)
                    .style('top', `${event.pageY - 28}px`);
            })
            .on('mouseout', function() {
                tooltip.transition().duration(250).style('opacity', 0);
            })
            .on('click', function(event, link) {
                const formulaNodeIndex = link.source.kind === 'formula' ? link.source.index : link.target.kind === 'formula' ? link.target.index : null;
                activeFormulaNode = activeFormulaNode === formulaNodeIndex ? null : formulaNodeIndex;
                updateLinkHighlight();
                event.stopPropagation();
            });

        const nodeGroups = chart.append('g')
            .selectAll('g')
            .data(graph.nodes)
            .enter()
            .append('g');

        nodeGroups.append('rect')
            .attr('x', node => node.x0)
            .attr('y', node => node.y0)
            .attr('width', node => node.x1 - node.x0)
            .attr('height', node => Math.max(1, node.y1 - node.y0))
            .attr('fill', node => {
                if (node.kind === 'tradition') {
                    return traditionColors[node.name] || '#cbd5e1';
                }
                if (node.kind === 'formula') {
                    return formulaColorScale(node.formulaId);
                }
                return '#795a42';
            })
            .attr('stroke', '#ffffff')
            .attr('stroke-width', 1)
            .on('mouseover', function(event, node) {
                tooltip.transition().duration(150).style('opacity', 0.95);
                tooltip.html(`${node.name}<br>Total flow: ${node.value || 0}<br>${formatPrayerListTooltip(node.items)}`)
                    .style('left', `${event.pageX + 5}px`)
                    .style('top', `${event.pageY - 28}px`);
            })
            .on('mouseout', function() {
                tooltip.transition().duration(250).style('opacity', 0);
            });

        nodeGroups.filter(node => node.kind !== 'formula').append('text')
            .attr('x', node => node.x0 < width / 2 ? node.x1 + 8 : node.x0 - 8)
            .attr('y', node => (node.y0 + node.y1) / 2)
            .attr('dy', '0.35em')
            .attr('font-size', 11)
            .attr('fill', '#111827')
            .attr('text-anchor', node => node.x0 < width / 2 ? 'start' : 'end')
            .text(node => truncateLabel(node.name, 24))
            .call(applyTextOutline, 4);

        svg.on('click', function(event) {
            if (event.target.tagName !== 'path') {
                activeFormulaNode = null;
                updateLinkHighlight();
            }
        });

        svg.call(
            d3.zoom().scaleExtent([0.75, 4]).on('zoom', function(event) {
                chart.attr('transform', `translate(${margin.left + event.transform.x},${margin.top + event.transform.y}) scale(${event.transform.k})`);
            })
        );
    }

    window.FormulasVisualizations = {
        render(options) {
            const renderers = {
                parallel: renderParallelCoordinates,
                dot_matrix: renderDotPlotMatrix,
                circos: renderCircosPlot,
                sankey: renderSankeyDiagram
            };

            const renderer = renderers[options.type] || renderParallelCoordinates;
            renderer(options);
        }
    };
})();
