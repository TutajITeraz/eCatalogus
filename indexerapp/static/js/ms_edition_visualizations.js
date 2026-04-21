(function() {
    const LOCAL_CHART_MIN_WIDTH = 720;
    const LOCAL_CHART_STEP_WIDTH = 28;

    function ensureTooltip() {
        let tooltip = d3.select('#edition-chart-tooltip');
        if (tooltip.empty()) {
            tooltip = d3.select('body')
                .append('div')
                .attr('id', 'edition-chart-tooltip')
                .attr('class', 'tooltip')
                .style('opacity', 0)
                .style('pointer-events', 'none');
        }
        return tooltip;
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

    function truncateLabel(text, maxLength = 90) {
        if (!text) {
            return '';
        }
        return text.length > maxLength ? `${text.substring(0, maxLength)}...` : text;
    }

    function getEditionText(item) {
        return item?.rubric_name_standarized || item?.rubric_name_from_ms || item?.rubric || item?.formula_text || 'No rite text available.';
    }

    function formatEditionTextTooltip(item) {
        return `Text: ${truncateLabel(getEditionText(item), 320)}`;
    }

    function collectEditionTexts(items, limit = 3) {
        return [...new Set((items || []).map(getEditionText).filter(Boolean))].slice(0, limit);
    }

    function formatEditionTextListTooltip(items) {
        const texts = collectEditionTexts(items);
        if (!texts.length) {
            return formatEditionTextTooltip(null);
        }
        return texts.map((text, index) => `Text ${index + 1}: ${truncateLabel(text, 220)}`).join('<br>');
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

    function buildEditionGroups(data) {
        return Array.from(d3.group(data, item => item.edition_index), ([editionIndex, items]) => ({
            editionIndex,
            items
        }));
    }

    function getEditionColorScale(editionGroups, colorPalette) {
        return d3.scaleOrdinal(d3.schemeCategory10).domain(editionGroups.map(group => group.editionIndex));
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
        let currentY = 0;

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
        const { containerSelector, data, colorPalette } = options;
        if (!data.length) {
            showEmptyState(containerSelector, 'No data available for the selected manuscripts.');
            return;
        }

        clearContainer(containerSelector);

        const tooltip = ensureTooltip();
        const margin = { top: 20, right: 30, bottom: 40, left: 250 };
        const { width, height } = getContainerDimensions(containerSelector, data, item => item.rubric_sequence, margin);
        const svg = d3.select(containerSelector)
            .append('svg')
            .attr('width', width + margin.left + margin.right)
            .attr('height', height + margin.top + margin.bottom);

        const chart = svg.append('g')
            .attr('transform', `translate(${margin.left},${margin.top})`);

        const x = d3.scaleLinear()
            .range([0, width])
            .domain(d3.extent(data, item => item.rubric_sequence));
        const manuscripts = [...new Set(data.map(item => item.Table))];
        const y = d3.scalePoint()
            .range([0, height])
            .padding(0.2)
            .domain(manuscripts);

        const editionGroups = buildEditionGroups(data);
        const color = getEditionColorScale(editionGroups, colorPalette);
        const line = d3.line()
            .x(item => x(item.rubric_sequence))
            .y(item => y(item.Table));

        let selectedEditionIndex = null;

        function highlightEdition(editionIndex) {
            selectedEditionIndex = editionIndex;
            chart.selectAll('path.data-line')
                .classed('selected-line', group => group.editionIndex === editionIndex);
            chart.selectAll('circle.parallel-point')
                .classed('selected-circle', item => item.edition_index === editionIndex);
        }

        chart.selectAll('path.data-line')
            .data(editionGroups)
            .enter()
            .append('path')
            .attr('class', 'data-line')
            .attr('fill', 'none')
            .attr('stroke', group => color(group.editionIndex))
            .attr('stroke-width', 3)
            .attr('d', group => line(group.items))
            .on('mouseover', function(event, group) {
                tooltip.transition().duration(150).style('opacity', 0.95);
                tooltip.html(`Edition: ${group.editionIndex}<br>${formatEditionTextTooltip(group.items[0])}`)
                    .style('left', `${event.pageX + 5}px`)
                    .style('top', `${event.pageY - 28}px`);
            })
            .on('mouseout', function() {
                tooltip.transition().duration(250).style('opacity', 0);
            })
            .on('click', function(event, group) {
                highlightEdition(group.editionIndex);
                event.stopPropagation();
            });

        chart.selectAll('circle.parallel-point')
            .data(data)
            .enter()
            .append('circle')
            .attr('class', 'parallel-point')
            .attr('r', 7)
            .attr('cx', item => x(item.rubric_sequence))
            .attr('cy', item => y(item.Table))
            .attr('fill', item => color(item.edition_index))
            .on('mouseover', function(event, item) {
                tooltip.transition().duration(150).style('opacity', 0.95);
                tooltip.html(`Edition: ${item.edition_index}<br>Rubric: ${item.rubric_sequence}<br>${formatEditionTextTooltip(item)}`)
                    .style('left', `${event.pageX + 5}px`)
                    .style('top', `${event.pageY - 28}px`);
            })
            .on('mouseout', function() {
                tooltip.transition().duration(250).style('opacity', 0);
            })
            .on('click', function(event, item) {
                highlightEdition(item.edition_index);
                event.stopPropagation();
            });

        chart.append('g')
            .attr('class', 'x axis')
            .attr('transform', `translate(0,${height})`)
            .call(d3.axisBottom(x));

        chart.append('g')
            .attr('class', 'y axis')
            .call(d3.axisLeft(y))
            .selectAll('text')
            .call(wrapAxisText, margin.left - 10)
            .call(applyTextOutline, 4);

        svg.on('click', function(event) {
            if (!d3.select(event.target).classed('parallel-point') && !d3.select(event.target).classed('data-line')) {
                selectedEditionIndex = null;
                chart.selectAll('.selected-line').classed('selected-line', false);
                chart.selectAll('.selected-circle').classed('selected-circle', false);
            }
        });

        svg.call(
            d3.zoom().on('zoom', function(event) {
                const newX = event.transform.rescaleX(x);
                chart.select('.x.axis').call(d3.axisBottom(newX));
                chart.selectAll('circle.parallel-point')
                    .attr('cx', item => newX(item.rubric_sequence));
                chart.selectAll('path.data-line')
                    .attr('d', group => d3.line()
                        .x(item => newX(item.rubric_sequence))
                        .y(item => y(item.Table))(group.items));
            })
        );
    }

    function renderDotPlotMatrix(options) {
        const { containerSelector, data, colorPalette } = options;
        if (!data.length) {
            showEmptyState(containerSelector, 'No data available for the selected manuscripts.');
            return;
        }

        const manuscripts = [...new Set(data.map(item => item.Table))];
        if (manuscripts.length < 2) {
            showEmptyState(containerSelector, 'Dot Plot Matrix needs at least two manuscripts.');
            return;
        }

        clearContainer(containerSelector);

        const tooltip = ensureTooltip();
        const leftManuscript = manuscripts[0];
        const rightManuscript = manuscripts[1];
        const editionGroups = buildEditionGroups(data);
        const pairData = [];
        editionGroups.forEach(group => {
            const byManuscript = d3.group(group.items, item => item.Table);
            const leftEntries = (byManuscript.get(leftManuscript) || []).slice().sort((a, b) => a.rubric_sequence - b.rubric_sequence);
            const rightEntries = (byManuscript.get(rightManuscript) || []).slice().sort((a, b) => a.rubric_sequence - b.rubric_sequence);
            if (!leftEntries.length || !rightEntries.length) {
                return;
            }
            const steps = Math.max(leftEntries.length, rightEntries.length);
            for (let index = 0; index < steps; index++) {
                pairData.push({
                    editionIndex: group.editionIndex,
                    left: leftEntries[Math.min(index, leftEntries.length - 1)],
                    right: rightEntries[Math.min(index, rightEntries.length - 1)]
                });
            }
        });

        if (!pairData.length) {
            showEmptyState(containerSelector, 'No shared edition pairs to plot for the selected manuscripts.');
            return;
        }

        const margin = { top: 30, right: 30, bottom: 70, left: 90 };
        const { width, height } = getContainerDimensions(containerSelector, pairData, item => item.left.rubric_sequence, margin);
        const svg = d3.select(containerSelector)
            .append('svg')
            .attr('width', width + margin.left + margin.right)
            .attr('height', height + margin.top + margin.bottom);

        const chart = svg.append('g')
            .attr('transform', `translate(${margin.left},${margin.top})`);

        const x = d3.scaleLinear().range([0, width]).domain(d3.extent(pairData, item => item.left.rubric_sequence));
        const y = d3.scaleLinear().range([height, 0]).domain(d3.extent(pairData, item => item.right.rubric_sequence));
        const color = getEditionColorScale(editionGroups, colorPalette);

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
            .attr('cx', item => x(item.left.rubric_sequence))
            .attr('cy', item => y(item.right.rubric_sequence))
            .attr('fill', item => color(item.editionIndex))
            .attr('stroke', 'white')
            .attr('stroke-width', 1.5)
            .on('mouseover', function(event, item) {
                tooltip.transition().duration(150).style('opacity', 0.95);
                tooltip.html(`Edition: ${item.editionIndex}<br>${leftManuscript}: ${item.left.rubric_sequence}<br>${rightManuscript}: ${item.right.rubric_sequence}<br>${formatEditionTextTooltip(item.left)}`)
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
        const { containerSelector, data, colorPalette } = options;
        if (!data.length) {
            showEmptyState(containerSelector, 'No data available for the selected manuscripts.');
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
        const editionGroups = buildEditionGroups(data);
        const color = getEditionColorScale(editionGroups, colorPalette);

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
                const [x, y] = polarToCartesian(angle, outerRadius + 62);
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
                positions.set(`${group.manuscript}::${value.edition_index}::${value.rubric_sequence}`, { angle, value, manuscript: group.manuscript });
            });
        });

        editionGroups.forEach(group => {
            const uniqueManuscripts = [...new Set(group.items.map(item => item.Table))];
            const groupColor = color(group.editionIndex);

            group.items.forEach(item => {
                const key = `${item.Table}::${item.edition_index}::${item.rubric_sequence}`;
                const point = positions.get(key);
                const [x, y] = polarToCartesian(point.angle, radius - 6);
                chart.append('circle')
                    .attr('cx', x)
                    .attr('cy', y)
                    .attr('r', 4)
                    .attr('fill', groupColor)
                    .attr('stroke', 'white')
                    .attr('stroke-width', 1.5)
                    .on('mouseover', function(event) {
                        tooltip.transition().duration(150).style('opacity', 0.95);
                        tooltip.html(`Edition: ${item.edition_index}<br>Manuscript: ${item.Table}<br>Rubric: ${item.rubric_sequence}<br>${formatEditionTextTooltip(item)}`)
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
                const source = positions.get(`${group.items[index].Table}::${group.items[index].edition_index}::${group.items[index].rubric_sequence}`);
                const target = positions.get(`${group.items[index + 1].Table}::${group.items[index + 1].edition_index}::${group.items[index + 1].rubric_sequence}`);
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
                    .attr('stroke', groupColor)
                    .attr('stroke-width', 2.5)
                    .attr('stroke-opacity', 0.75)
                    .on('mouseover', function(event) {
                        tooltip.transition().duration(150).style('opacity', 0.95);
                        tooltip.html(`Edition: ${group.editionIndex}<br>${formatEditionTextTooltip(group.items[0])}`)
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
        const { containerSelector, data, colorPalette } = options;
        if (!data.length) {
            showEmptyState(containerSelector, 'No data available for the selected manuscripts.');
            return;
        }
        if (typeof d3.sankey !== 'function') {
            showEmptyState(containerSelector, 'Sankey renderer is unavailable because d3-sankey is not loaded.');
            return;
        }

        clearContainer(containerSelector);

        const tooltip = ensureTooltip();
        const margin = { top: 20, right: 30, bottom: 20, left: 20 };
        const { width, height } = getContainerDimensions(containerSelector, data, item => item.rubric_sequence, margin);
        const svg = d3.select(containerSelector)
            .append('svg')
            .attr('width', width + margin.left + margin.right);

        const editionGroups = buildEditionGroups(data);
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
            const editionKey = `edition:${item.edition_index}`;
            const manuscriptNode = ensureNode(manuscriptKey, { name: item.Table, kind: 'manuscript', items: [] });
            const editionNode = ensureNode(editionKey, { name: `Edition ${item.edition_index}`, kind: 'edition', editionIndex: item.edition_index, items: [] });
            const linkKey = `${manuscriptNode}->${editionNode}`;

            nodes[manuscriptNode].items.push(item);
            nodes[editionNode].items.push(item);

            if (!links.has(linkKey)) {
                links.set(linkKey, { source: manuscriptNode, target: editionNode, value: 0, editionIndex: item.edition_index, items: [] });
            }
            links.get(linkKey).value += 1;
            links.get(linkKey).items.push(item);
        });

        const maxColumnNodes = Math.max(
            nodes.filter(node => node.kind === 'manuscript').length,
            nodes.filter(node => node.kind === 'edition').length,
            1
        );
        const sankeyHeight = Math.max(420, Math.min(Math.max(height, 420), maxColumnNodes * 42));
        svg.attr('height', sankeyHeight + margin.top + margin.bottom);

        const chart = svg.append('g')
            .attr('transform', `translate(${margin.left},${margin.top})`);

        const sankey = d3.sankey()
            .nodeWidth(18)
            .nodePadding(Math.max(42, Math.floor(sankeyHeight / (maxColumnNodes * 2.2))))
            .nodeAlign(node => node.kind === 'manuscript' ? 0 : 1)
            .nodeSort((left, right) => left.name.localeCompare(right.name))
            .extent([[0, 0], [width, sankeyHeight]]);

        const graph = sankey({
            nodes: nodes.map(node => ({ ...node })),
            links: Array.from(links.values()).map(link => ({ ...link }))
        });

        distributeNodesVertically(graph.nodes.filter(node => node.kind === 'edition'), sankeyHeight, 10);
        sankey.update(graph);

        const color = getEditionColorScale(editionGroups, colorPalette);
        let activeEditionNode = null;

        function linkColor(link) {
            if (activeEditionNode && (link.source.index === activeEditionNode || link.target.index === activeEditionNode)) {
                return '#111111';
            }
            return color(link.editionIndex);
        }

        function updateLinkHighlight() {
            chart.selectAll('path.sankey-link')
                .attr('stroke', linkColor)
                .attr('stroke-opacity', link => (activeEditionNode && (link.source.index === activeEditionNode || link.target.index === activeEditionNode)) ? 0.95 : 0.45);
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
                tooltip.html(`${link.source.name} -> ${link.target.name}<br>Weight (number of linked occurrences): ${link.value}<br>${formatEditionTextListTooltip(link.items)}`)
                    .style('left', `${event.pageX + 5}px`)
                    .style('top', `${event.pageY - 28}px`);
            })
            .on('mouseout', function() {
                tooltip.transition().duration(250).style('opacity', 0);
            })
            .on('click', function(event, link) {
                const editionNodeIndex = link.source.kind === 'edition' ? link.source.index : link.target.kind === 'edition' ? link.target.index : null;
                activeEditionNode = activeEditionNode === editionNodeIndex ? null : editionNodeIndex;
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
            .attr('fill', node => node.kind === 'edition' ? color(node.editionIndex) : '#795a42')
            .attr('stroke', '#ffffff')
            .attr('stroke-width', 1)
            .on('mouseover', function(event, node) {
                tooltip.transition().duration(150).style('opacity', 0.95);
                tooltip.html(`${node.name}<br>Total flow: ${node.value || 0}<br>${formatEditionTextListTooltip(node.items)}`)
                    .style('left', `${event.pageX + 5}px`)
                    .style('top', `${event.pageY - 28}px`);
            })
            .on('mouseout', function() {
                tooltip.transition().duration(250).style('opacity', 0);
            });

        nodeGroups.append('text')
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
                activeEditionNode = null;
                updateLinkHighlight();
            }
        });

    }

    window.EditionVisualizations = {
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
