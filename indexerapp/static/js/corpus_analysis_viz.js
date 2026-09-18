/*
 * Renderers for the corpus analysis page.
 *
 * Every function here draws from artifacts a run already produced. Nothing is
 * computed from raw content: if a number is on screen, it came out of a file.
 *
 * Kept separate from corpus_analysis.js the same way ms_formulas_visualizations.js
 * is kept apart from ms_formulas_graph.js — page wiring in one file, drawing in
 * the other.
 */
window.CorpusAnalysisViz = (function () {
  'use strict';

  const palette = [
    '#e6194B', '#3cb44b', '#4363d8', '#f58231', '#911eb4',
    '#42d4f4', '#f032e6', '#bfef45', '#469990', '#9A6324',
    '#800000', '#808000', '#000075', '#a9a9a9', '#fabed4',
    '#dcbeff', '#aaffc3', '#ffd8b1'
  ];

  let tooltip = null;

  function ensureTooltip() {
    if (tooltip) return tooltip;
    tooltip = d3.select('body').append('div')
      .attr('class', 'corpus-tooltip')
      .style('position', 'absolute')
      .style('pointer-events', 'none')
      .style('background', 'rgba(13,27,42,0.94)')
      .style('color', '#fff')
      .style('padding', '6px 9px')
      .style('border-radius', '4px')
      .style('font-size', '12px')
      .style('max-width', '380px')
      .style('z-index', 9999)
      .style('display', 'none');
    return tooltip;
  }

  function showTooltip(html, event) {
    ensureTooltip()
      .html(html)
      .style('display', 'block')
      .style('left', (event.pageX + 14) + 'px')
      .style('top', (event.pageY - 12) + 'px');
  }

  function hideTooltip() {
    if (tooltip) tooltip.style('display', 'none');
  }

  function colorFor(index) {
    if (index === null || index === undefined || index < 0) return '#c9c9c9';
    return palette[index % palette.length];
  }

  function clear(selector) {
    const node = document.querySelector(selector);
    if (node) node.innerHTML = '';
    return node;
  }

  function message(selector, text) {
    const node = clear(selector);
    if (node) {
      node.innerHTML =
        '<div class="text-center py-10 text-gray-600 font-semibold">' + text + '</div>';
    }
  }

  function dimensions(selector, fallbackHeight) {
    const node = document.querySelector(selector);
    const width = node && node.clientWidth ? node.clientWidth : 900;
    const height = node && node.clientHeight ? node.clientHeight : (fallbackHeight || 600);
    return { width: Math.max(width, 320), height: Math.max(height, 320) };
  }

  /* ------------------------------------------------------------------ *
   * Condensed matrices
   * ------------------------------------------------------------------ */

  /**
   * Index into a condensed upper triangle stored row-major without the diagonal,
   * which is how matrices.json stores every metric.
   */
  function condensedIndex(n, i, j) {
    if (i === j) return -1;
    if (i > j) { const t = i; i = j; j = t; }
    return (n * i) - ((i * (i + 1)) / 2) + (j - i - 1);
  }

  function matrixValue(matrices, metric, n, i, j) {
    if (i === j) return metric === 'mean_displacement' ? 0 : 1;
    const values = matrices.metrics[metric];
    if (!values) return 0;
    return values[condensedIndex(n, i, j)];
  }

  /* ------------------------------------------------------------------ *
   * Dendrogram geometry
   * ------------------------------------------------------------------ */

  function dendrogramSegments(linkage, n, leafOrder) {
    const positions = new Array(2 * n - 1);
    leafOrder.forEach(function (leaf, slot) {
      positions[leaf] = { x: slot + 0.5, y: 0 };
    });

    const segments = [];
    let maxHeight = 0;
    linkage.forEach(function (row, k) {
      const left = Math.round(row[0]);
      const right = Math.round(row[1]);
      const height = row[2];
      const a = positions[left];
      const b = positions[right];
      if (!a || !b) return;
      positions[n + k] = { x: (a.x + b.x) / 2, y: height };
      segments.push([a.x, a.y, a.x, height]);
      segments.push([b.x, b.y, b.x, height]);
      segments.push([a.x, height, b.x, height]);
      maxHeight = Math.max(maxHeight, height);
    });
    return { segments: segments, maxHeight: maxHeight || 1 };
  }

  /* ------------------------------------------------------------------ *
   * 1. Similarity heatmap with dendrograms
   * ------------------------------------------------------------------ */

  function renderHeatmap(options) {
    const { selector, manuscripts, matrices, clusters, metric, onSelectPair } = options;
    const n = matrices.n;
    if (!n || n < 2) {
      return message(selector, 'This comparison group has fewer than two manuscripts to compare.');
    }

    const order = (clusters.leaf_order && clusters.leaf_order.length)
      ? clusters.leaf_order : d3.range(n);
    const higherIsCloser = matrices.higher_is_closer[metric] !== false;

    const node = clear(selector);
    const size = dimensions(selector, 640);
    const treeSize = 74;
    const labelSize = 210;
    // bottom has to clear the colour ramp and its labels, which renderLegend
    // draws 22px below the grid.
    const margin = { top: treeSize + 10, right: 22, bottom: 34, left: labelSize };

    const available = Math.min(
      size.width - margin.left - margin.right,
      Math.max(size.height - margin.top - margin.bottom, 240)
    );
    const cell = Math.max(Math.min(available / n, 46), 8);
    const grid = cell * n;

    const svg = d3.select(node).append('svg')
      .attr('width', margin.left + grid + margin.right)
      .attr('height', margin.top + grid + margin.bottom)
      .attr('class', 'printIt')
      .style('background', '#fff');

    const values = [];
    for (let i = 0; i < n; i++) {
      for (let j = 0; j < n; j++) {
        if (i !== j) values.push(matrixValue(matrices, metric, n, i, j));
      }
    }
    const extent = d3.extent(values);
    const scale = d3.scaleSequential(
      higherIsCloser ? d3.interpolateYlGnBu : d3.interpolateYlOrRd
    ).domain(higherIsCloser ? extent : [extent[1], extent[0]]);

    const plot = svg.append('g')
      .attr('transform', 'translate(' + margin.left + ',' + margin.top + ')');

    // Cells
    order.forEach(function (rowMs, rowSlot) {
      order.forEach(function (colMs, colSlot) {
        const value = matrixValue(matrices, metric, n, rowMs, colMs);
        plot.append('rect')
          .attr('x', colSlot * cell)
          .attr('y', rowSlot * cell)
          .attr('width', cell - 1)
          .attr('height', cell - 1)
          .attr('fill', rowMs === colMs ? '#f0e6dc' : scale(value))
          .style('cursor', rowMs === colMs ? 'default' : 'pointer')
          .on('mousemove', function (event) {
            if (rowMs === colMs) return;
            showTooltip(
              '<strong>' + manuscripts[rowMs].label + '</strong><br>' +
              '<strong>' + manuscripts[colMs].label + '</strong><br>' +
              metric.replace(/_/g, ' ') + ': ' + value.toFixed(3),
              event
            );
          })
          .on('mouseleave', hideTooltip)
          .on('click', function () {
            hideTooltip();
            if (rowMs !== colMs && onSelectPair) onSelectPair(rowMs, colMs);
          });
      });
    });

    // Row labels
    plot.selectAll('text.row-label')
      .data(order)
      .enter().append('text')
      .attr('class', 'row-label')
      .attr('x', -8)
      .attr('y', function (d, i) { return i * cell + cell / 2; })
      .attr('text-anchor', 'end')
      .attr('dominant-baseline', 'middle')
      .attr('font-size', Math.min(Math.max(cell * 0.6, 8), 12))
      .attr('fill', '#0d1b2a')
      .text(function (d) {
        const label = manuscripts[d].label;
        return label.length > 34 ? label.slice(0, 33) + '…' : label;
      });

    // Dendrogram above the columns, mirroring the seriation order.
    if (clusters.linkage && clusters.linkage.length) {
      const tree = dendrogramSegments(clusters.linkage, n, order);
      const x = d3.scaleLinear().domain([0, n]).range([0, grid]);
      const y = d3.scaleLinear().domain([0, tree.maxHeight]).range([0, treeSize]);
      const top = svg.append('g')
        .attr('transform', 'translate(' + margin.left + ',' + (margin.top - 6) + ')');
      tree.segments.forEach(function (s) {
        top.append('line')
          .attr('x1', x(s[0])).attr('y1', -y(s[1]))
          .attr('x2', x(s[2])).attr('y2', -y(s[3]))
          .attr('stroke', '#795a42')
          .attr('stroke-width', 1.2);
      });
    }

    renderLegend(svg, scale, extent, metric, higherIsCloser,
      margin.left, margin.top + grid + 4, Math.min(grid, 260));
  }

  function renderLegend(svg, scale, extent, metric, higherIsCloser, x, y, width) {
    const steps = 40;
    const group = svg.append('g').attr('transform', 'translate(' + x + ',' + y + ')');
    for (let i = 0; i < steps; i++) {
      const t = i / (steps - 1);
      group.append('rect')
        .attr('x', (width / steps) * i)
        .attr('y', 0)
        .attr('width', width / steps + 0.5)
        .attr('height', 7)
        .attr('fill', scale(extent[0] + t * (extent[1] - extent[0])));
    }
    group.append('text')
      .attr('x', 0).attr('y', 18).attr('font-size', 10).attr('fill', '#555')
      .text(extent[0].toFixed(2));
    group.append('text')
      .attr('x', width).attr('y', 18).attr('text-anchor', 'end')
      .attr('font-size', 10).attr('fill', '#555')
      .text(extent[1].toFixed(2));
    group.append('text')
      .attr('x', width / 2).attr('y', 18).attr('text-anchor', 'middle')
      .attr('font-size', 10).attr('fill', '#555')
      .text(metric.replace(/_/g, ' ') + (higherIsCloser ? ' (higher = closer)' : ' (lower = closer)'));
  }

  /* ------------------------------------------------------------------ *
   * 2. MDS map of manuscripts
   * ------------------------------------------------------------------ */

  function renderMdsMap(options) {
    const { selector, manuscripts, embedding, clusters, colorBy, onSelect } = options;
    const coordinates = embedding.coordinates || [];
    if (coordinates.length < 2) {
      return message(selector, 'Not enough manuscripts to place on a map.');
    }

    const node = clear(selector);
    const size = dimensions(selector, 620);
    const margin = { top: 24, right: 24, bottom: 42, left: 24 };
    const width = size.width - margin.left - margin.right;
    const height = size.height - margin.top - margin.bottom;

    const svg = d3.select(node).append('svg')
      .attr('width', size.width)
      .attr('height', size.height)
      .attr('class', 'printIt')
      .style('background', '#fff');
    const plot = svg.append('g')
      .attr('transform', 'translate(' + margin.left + ',' + margin.top + ')');

    const x = d3.scaleLinear()
      .domain(d3.extent(coordinates, function (c) { return c[0]; })).nice()
      .range([30, width - 30]);
    const y = d3.scaleLinear()
      .domain(d3.extent(coordinates, function (c) { return c[1]; })).nice()
      .range([height - 30, 30]);

    const cut = clusters.suggested_k ? clusters.cuts[String(clusters.suggested_k)] : null;

    function pointColor(i) {
      if (colorBy === 'cluster' && cut) return colorFor(cut[i] - 1);
      if (colorBy === 'century') {
        const year = manuscripts[i].year_from;
        if (!year) return '#c9c9c9';
        return d3.interpolateViridis(Math.min(Math.max((year - 700) / 600, 0), 1));
      }
      if (colorBy === 'layer') {
        const profile = manuscripts[i].layer_profile || [];
        if (!profile.length) return '#c9c9c9';
        return colorFor(profile.indexOf(Math.max.apply(null, profile)));
      }
      const profile = manuscripts[i].tradition_profile || [];
      if (!profile.length) return '#c9c9c9';
      const attributed = profile.slice(0, -1);
      if (!attributed.length || Math.max.apply(null, attributed) <= 0) return '#c9c9c9';
      return colorFor(attributed.indexOf(Math.max.apply(null, attributed)));
    }

    const sizeScale = d3.scaleSqrt()
      .domain(d3.extent(manuscripts, function (m) { return m.n_distinct; }))
      .range([6, 20]);

    manuscripts.forEach(function (ms, i) {
      const cx = x(coordinates[i][0]);
      const cy = y(coordinates[i][1]);
      plot.append('circle')
        .attr('cx', cx).attr('cy', cy)
        .attr('r', sizeScale(ms.n_distinct))
        .attr('fill', pointColor(i))
        .attr('fill-opacity', 0.78)
        .attr('stroke', '#0d1b2a')
        .attr('stroke-width', 0.8)
        .style('cursor', 'pointer')
        .on('mousemove', function (event) {
          showTooltip(
            '<strong>' + ms.label + '</strong><br>' +
            (ms.shelf_mark || '') + '<br>' +
            ms.n_distinct + ' distinct formulas, ' + ms.n_items + ' occurrences' +
            (ms.year_from ? '<br>' + ms.year_from + '–' + ms.year_to : ''),
            event
          );
        })
        .on('mouseleave', hideTooltip)
        .on('click', function () { if (onSelect) onSelect(i); });

      plot.append('text')
        .attr('x', cx).attr('y', cy - sizeScale(ms.n_distinct) - 4)
        .attr('text-anchor', 'middle')
        .attr('font-size', 10)
        .attr('fill', '#0d1b2a')
        .text(ms.label.length > 26 ? ms.label.slice(0, 25) + '…' : ms.label);
    });

    svg.append('text')
      .attr('x', margin.left).attr('y', size.height - 12)
      .attr('font-size', 11).attr('fill', '#666')
      .text('Principal coordinates on 1 − idf-weighted cosine. '
        + (embedding.explained
          ? 'Two axes carry ' + Math.round(embedding.explained * 100) + '% of the variation.'
          : ''));
  }

  /* ------------------------------------------------------------------ *
   * 3. Seriation matrix of formula presence
   * ------------------------------------------------------------------ */

  function renderSeriation(options) {
    const { selector, presence } = options;
    const rows = presence.rows || [];
    const columns = presence.manuscript_labels || [];
    if (!rows.length) {
      return message(selector, 'No presence data in this comparison group.');
    }

    const node = clear(selector);
    const size = dimensions(selector, 620);
    const margin = { top: 150, right: 20, bottom: 30, left: 20 };
    const width = Math.max(size.width - margin.left - margin.right, 240);
    const height = Math.max(size.height - margin.top - margin.bottom, 240);

    const wrapper = d3.select(node).append('div').attr('class', 'printIt relative');

    // Column headers stay as real text so they survive printing; the cells are
    // drawn to canvas because a full corpus reaches millions of them and SVG
    // would not survive that.
    const columnWidth = width / columns.length;
    const header = wrapper.append('svg')
      .attr('width', size.width)
      .attr('height', margin.top)
      .style('display', 'block');
    columns.forEach(function (label, index) {
      header.append('text')
        .attr('transform', 'translate(' +
          (margin.left + columnWidth * (index + 0.5)) + ',' + (margin.top - 6) + ') rotate(-62)')
        .attr('font-size', 11)
        .attr('fill', '#0d1b2a')
        .text(label.length > 26 ? label.slice(0, 25) + '…' : label);
    });

    const canvas = wrapper.append('canvas')
      .attr('class', 'printIt')
      .attr('width', width)
      .attr('height', height)
      .style('margin-left', margin.left + 'px')
      .style('border', '1px solid #e3d5ca')
      .node();

    const context = canvas.getContext('2d');
    context.fillStyle = '#ffffff';
    context.fillRect(0, 0, width, height);

    const rowHeight = height / rows.length;
    context.fillStyle = '#795a42';
    rows.forEach(function (witnesses, rowIndex) {
      const y = rowIndex * rowHeight;
      witnesses.forEach(function (column) {
        context.fillRect(
          column * columnWidth, y,
          Math.max(columnWidth - 1, 1), Math.max(rowHeight, 0.6)
        );
      });
    });

    wrapper.append('p')
      .attr('class', 'printIt text-xs text-gray-600 mt-2')
      .style('margin-left', margin.left + 'px')
      .text(rows.length + ' formulas (rows) across ' + columns.length +
        ' manuscripts (columns), both in seriation order. Solid blocks are shared '
        + 'repertoire; ragged columns are material unique to one witness.');
  }

  /* ------------------------------------------------------------------ *
   * 4. Repertoire layers
   * ------------------------------------------------------------------ */

  function renderLayers(options) {
    const { selector, layers } = options;
    if (!layers || !layers.manuscript_shares) {
      return message(selector, 'This comparison group was too small to factor into liturgical clusters.');
    }

    const node = clear(selector);
    const shares = layers.manuscript_shares;
    const k = layers.k;
    const size = dimensions(selector, 560);
    const margin = { top: 30, right: 20, bottom: 40, left: 240 };
    const width = Math.max(size.width - margin.left - margin.right, 260);
    const barHeight = 26;
    const height = shares.length * (barHeight + 8);

    const svg = d3.select(node).append('svg')
      .attr('width', margin.left + width + margin.right)
      .attr('height', margin.top + height + margin.bottom)
      .attr('class', 'printIt')
      .style('background', '#fff');
    const plot = svg.append('g')
      .attr('transform', 'translate(' + margin.left + ',' + margin.top + ')');

    shares.forEach(function (entry, row) {
      const y = row * (barHeight + 8);
      let offset = 0;
      entry.shares.forEach(function (share, layerIndex) {
        const w = share * width;
        if (w <= 0) return;
        plot.append('rect')
          .attr('x', offset).attr('y', y)
          .attr('width', w).attr('height', barHeight)
          .attr('fill', colorFor(layerIndex))
          .on('mousemove', function (event) {
            showTooltip(
              '<strong>' + entry.label + '</strong><br>Cluster ' + (layerIndex + 1) +
              ': ' + Math.round(share * 100) + '%',
              event
            );
          })
          .on('mouseleave', hideTooltip);
        offset += w;
      });
      plot.append('text')
        .attr('x', -10).attr('y', y + barHeight / 2)
        .attr('text-anchor', 'end').attr('dominant-baseline', 'middle')
        .attr('font-size', 12).attr('fill', '#0d1b2a')
        .text(entry.label.length > 38 ? entry.label.slice(0, 37) + '…' : entry.label);
    });

    const legend = svg.append('g')
      .attr('transform', 'translate(' + margin.left + ',' + (margin.top + height + 18) + ')');
    for (let i = 0; i < k; i++) {
      legend.append('rect')
        .attr('x', i * 110).attr('y', 0).attr('width', 12).attr('height', 12)
        .attr('fill', colorFor(i));
      legend.append('text')
        .attr('x', i * 110 + 17).attr('y', 10)
        .attr('font-size', 11).attr('fill', '#333')
        .text('Cluster ' + (i + 1));
    }
  }

  function renderLayerTable(selector, layers) {
    const node = clear(selector);
    if (!layers || !layers.layers) return;

    const html = layers.layers.map(function (layer) {
      const rows = layer.top_formulas.slice(0, 12).map(function (f) {
        return '<tr>' +
          '<td class="pr-3 whitespace-nowrap">' +
          prayerMarkup(f.co_no || '—', f.uuid) + '</td>' +
          '<td class="pr-3">' +
          prayerMarkup(f.incipit, f.uuid, { quiet: true }) + '</td>' +
          '<td class="pr-3 whitespace-nowrap">' + escapeHtml((f.traditions || []).join(', ') || '—') + '</td>' +
          '<td class="text-right">' + f.distinctiveness.toFixed(2) + '</td>' +
          '</tr>';
      }).join('');
      return '<div class="printIt mb-5">' +
        '<h4 class="caudex-bold text-lg mb-1" style="color:' + colorFor(layer.index) + '">' +
        'Cluster ' + (layer.index + 1) + '</h4>' +
        '<table class="text-sm w-full"><thead><tr class="text-gray-500 text-left">' +
        '<th class="pr-3">CO no.</th><th class="pr-3">Incipit</th>' +
        '<th class="pr-3">Known tradition</th><th class="text-right">Distinctiveness</th>' +
        '</tr></thead><tbody>' + rows + '</tbody></table></div>';
    }).join('');

    node.innerHTML = html;
  }

  /* ------------------------------------------------------------------ *
   * 5. Report
   * ------------------------------------------------------------------ */

  function escapeHtml(value) {
    if (value === null || value === undefined) return '';
    return String(value)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  /* ------------------------------------------------------------------ *
   * Prayer references inside report tables
   * ------------------------------------------------------------------ */

  /**
   * Columns whose cells name prayers in artifacts written before the report
   * carried formula uuids. Those cells are plain strings, so the CO number is
   * all there is to go on — which is ambiguous, but still far better than a
   * bare number that means nothing. Runs written since carry the uuid and never
   * reach this path.
   */
  const LEGACY_PRAYER_COLUMNS = {
    'CO no.': null,
    'Prayers': ' → ',
    'Characteristic formulas': '; ',
  };

  /** What a CO number looks like: a number, optionally with a letter suffix. */
  const CO_NUMBER = /^[0-9]{1,6}(\s?[a-zA-Z]{1,4})?$/;

  /**
   * @param {{co?: boolean, quiet?: boolean}} [options] see PrayerHover.markup.
   */
  function prayerMarkup(text, reference, options) {
    if (window.PrayerHover) return window.PrayerHover.markup(text, reference, options);
    return escapeHtml(text);
  }

  function legacyPrayerCell(value, separator) {
    if (separator === null) {
      return CO_NUMBER.test(value.trim())
        ? prayerMarkup(value, value.trim(), { co: true }) : escapeHtml(value);
    }
    return value.split(separator).map(function (part) {
      const token = part.trim();
      return CO_NUMBER.test(token)
        ? prayerMarkup(part, token, { co: true }) : escapeHtml(part);
    }).join(escapeHtml(separator));
  }

  /**
   * One table cell.
   *
   * A cell is normally a string or a number. It may also be a prayer reference
   * — `{t: displayed text, f: formula uuid}` — or a list mixing references with
   * the plain separators that stand between them, which is how a cell naming
   * several prayers keeps each one hoverable on its own.
   */
  function renderCell(cell, column) {
    if (Array.isArray(cell)) {
      return cell.map(function (token) { return renderCell(token, column); }).join('');
    }
    if (cell && typeof cell === 'object') {
      // A bare CO number has to advertise that it can be hovered; a whole incipit
      // would only be underlined from margin to margin for nothing.
      return prayerMarkup(cell.t, cell.f, { quiet: !CO_NUMBER.test(String(cell.t).trim()) });
    }
    if (typeof cell === 'string' && Object.prototype.hasOwnProperty.call(
      LEGACY_PRAYER_COLUMNS, column)) {
      return legacyPrayerCell(cell, LEGACY_PRAYER_COLUMNS[column]);
    }
    return escapeHtml(cell);
  }

  function renderReport(selector, report) {
    const node = clear(selector);
    if (!report || !report.sections) {
      return message(selector, 'This run produced no report.');
    }

    const html = report.sections.map(function (section) {
      const highlights = section.highlights.length
        ? '<div class="printIt flex flex-wrap gap-4 my-3">' + section.highlights.map(function (h) {
          return '<div class="px-3 py-2 bg-[#fef9f6] border border-[#e3d5ca] rounded">' +
            '<div class="text-xs text-gray-500">' + escapeHtml(h.label) + '</div>' +
            '<div class="text-lg caudex-bold">' + escapeHtml(h.value) + '</div></div>';
        }).join('') + '</div>'
        : '';

      const paragraphs = section.paragraphs.map(function (p) {
        return '<p class="printIt my-2 leading-relaxed">' + escapeHtml(p) + '</p>';
      }).join('');

      const tables = section.tables.filter(function (t) { return t.rows.length; })
        .map(function (table) {
          const head = table.columns.map(function (c) {
            return '<th class="pr-3 pb-1 text-left">' + escapeHtml(c) + '</th>';
          }).join('');
          const body = table.rows.map(function (row) {
            return '<tr class="border-t border-[#efe6de]">' + row.map(function (cell, index) {
              return '<td class="pr-3 py-1 align-top">' +
                renderCell(cell, table.columns[index]) + '</td>';
            }).join('') + '</tr>';
          }).join('');
          const note = table.note
            ? '<p class="text-xs text-gray-500 mt-1">' + escapeHtml(table.note) + '</p>' : '';
          return '<div class="printIt my-4 overflow-x-auto">' +
            '<h4 class="caudex-bold text-base mb-1">' + escapeHtml(table.title) + '</h4>' +
            '<table class="text-sm w-full"><thead><tr class="text-gray-500">' + head +
            '</tr></thead><tbody>' + body + '</tbody></table>' + note + '</div>';
        }).join('');

      return '<section class="mb-8">' +
        '<h3 class="printIt title caudex-bold text-2xl mt-6 mb-2 text-[#0d1b2a]">' +
        escapeHtml(section.title) + '</h3>' +
        paragraphs + highlights + tables + '</section>';
    }).join('');

    node.innerHTML = html;
  }

  /* ------------------------------------------------------------------ *
   * 6. Pair detail panel
   * ------------------------------------------------------------------ */

  function renderPairDetail(selector, options) {
    const { a, b, manuscripts, matrices, compareUrl } = options;
    const node = clear(selector);
    const n = matrices.n;

    const rows = Object.keys(matrices.metrics).map(function (metric) {
      const value = matrixValue(matrices, metric, n, a, b);
      return '<tr class="border-t border-[#efe6de]">' +
        '<td class="pr-4 py-1">' + escapeHtml(metric.replace(/_/g, ' ')) + '</td>' +
        '<td class="text-right py-1">' + value.toFixed(3) + '</td></tr>';
    }).join('');

    node.innerHTML =
      '<div class="printIt border border-[#e3d5ca] rounded p-3 bg-[#fffdfb]">' +
      '<h4 class="caudex-bold text-lg mb-1">' + escapeHtml(manuscripts[a].label) + '</h4>' +
      '<h4 class="caudex-bold text-lg mb-2">' + escapeHtml(manuscripts[b].label) + '</h4>' +
      '<table class="text-sm w-full"><tbody>' + rows + '</tbody></table>' +
      '<a class="inline-block mt-3 py-1 px-3 bg-[#795a42] hover:bg-[#997a62] text-white ' +
      'font-semibold rounded drop-shadow text-sm" href="' + compareUrl + '">' +
      'Open in Dot Plot Matrix</a></div>';
  }

  return {
    palette: palette,
    colorFor: colorFor,
    message: message,
    escapeHtml: escapeHtml,
    matrixValue: matrixValue,
    renderHeatmap: renderHeatmap,
    renderMdsMap: renderMdsMap,
    renderSeriation: renderSeriation,
    renderLayers: renderLayers,
    renderLayerTable: renderLayerTable,
    renderReport: renderReport,
    renderCell: renderCell,
    renderPairDetail: renderPairDetail,
    hideTooltip: hideTooltip
  };
})();
