/*
 * Corpus analysis page.
 *
 * Loads artifacts a background run already produced and hands them to the
 * renderers in corpus_analysis_viz.js. The only thing this page can start is a new
 * run; it never computes a metric itself.
 */

let corpusAnalysisState = {
  runs: [],
  run: null,
  manifest: null,
  cohort: null,
  metric: 'idf_cosine',
  colorBy: 'tradition',
  cache: {},
  activeTab: 'report',
  pollTimer: null,
  // Which manuscripts the *next* run will cover. `chosen` holds uuids explicitly
  // rather than exclusions, so a manuscript indexed after the picker was opened
  // never joins a selection behind the reader's back.
  selection: {
    loaded: false,
    manuscripts: [],
    genres: [],
    chosen: new Set(),
    filter: ''
  }
};

/** Stands for "under no genre at all" wherever a genre uuid is expected. */
const CORPUS_UNGROUPED = 'ungrouped';

function corpusArtifactUrl(runUuid, cohort, kind) {
  return pageRoot + '/analysis/runs/' + runUuid + '/' + cohort + '/' + kind + '/';
}

async function corpusFetchArtifact(cohort, kind) {
  const state = corpusAnalysisState;
  const key = state.run.uuid + '/' + cohort + '/' + kind;
  if (state.cache[key] !== undefined) return state.cache[key];

  const response = await fetch(corpusArtifactUrl(state.run.uuid, cohort, kind), {
    credentials: 'include'
  });
  if (!response.ok) {
    state.cache[key] = null;
    return null;
  }
  const payload = await response.json();
  state.cache[key] = payload;
  return payload;
}

function corpusSetStatus(text, tone) {
  const node = document.getElementById('corpusStatus');
  if (!node) return;
  node.textContent = text || '';
  node.className = 'text-sm ' + (tone === 'error' ? 'text-red-600' : 'text-gray-600');
}

function corpusShowProgress(run) {
  const wrapper = document.getElementById('corpusProgressWrapper');
  const bar = document.getElementById('corpusProgressBar');
  const label = document.getElementById('corpusProgressLabel');
  if (!wrapper) return;

  const active = run && (run.status === 'running' || run.status === 'pending');
  wrapper.style.display = active ? 'block' : 'none';
  if (active) {
    bar.style.width = (run.progress || 0) + '%';
    label.textContent = (run.progress || 0) + '% — ' + (run.stage || run.status);
  }
}

/* ---------------------------------------------------------------- *
 * Loading
 * ---------------------------------------------------------------- */

async function corpusLoadRuns(preferredUuid) {
  const response = await fetch(pageRoot + '/analysis/runs/', { credentials: 'include' });
  if (!response.ok) {
    corpusSetStatus('Could not load the list of analysis runs.', 'error');
    return;
  }
  const data = await response.json();
  corpusAnalysisState.runs = data.runs;

  const startButton = document.getElementById('corpusStartButton');
  if (startButton) startButton.style.display = data.can_start ? 'inline-block' : 'none';
  // Choosing a corpus is only of use to an account that can then run it.
  const selectionToggle = document.getElementById('corpusSelectionToggle');
  if (selectionToggle) {
    selectionToggle.style.display = data.can_start ? 'inline-block' : 'none';
  }

  const select = document.getElementById('corpusRunSelect');
  select.innerHTML = '';
  data.runs.forEach(function (run) {
    const option = document.createElement('option');
    const when = new Date(run.created_at).toLocaleString();
    const summary = run.summary && run.summary.manuscripts
      ? run.summary.manuscripts + ' mss' : run.status;
    option.value = run.uuid;
    option.textContent = when + ' — ' + summary +
      (run.status !== 'done' ? ' [' + run.status + ']' : '');
    select.appendChild(option);
  });

  if (!data.runs.length) {
    corpusSetStatus('No analysis has been run yet.');
    CorpusAnalysisViz.message('#corpusReport',
      'No analysis run exists yet. An editorial account can start one with the button above.');
    return;
  }

  const target = data.runs.find(function (r) { return r.uuid === preferredUuid; })
    || data.runs.find(function (r) { return r.status === 'done'; })
    || data.runs[0];
  select.value = target.uuid;
  await corpusSelectRun(target.uuid);
}

async function corpusSelectRun(uuid) {
  const state = corpusAnalysisState;
  state.run = state.runs.find(function (r) { return r.uuid === uuid; });
  if (!state.run) return;

  corpusShowProgress(state.run);
  if (state.run.status === 'running' || state.run.status === 'pending') {
    corpusSetStatus('This run is still in progress.');
    corpusStartPolling(uuid);
    return;
  }
  if (state.run.status === 'failed') {
    corpusSetStatus('This run failed: ' + (state.run.error || '').split('\n')[0], 'error');
    return;
  }

  state.manifest = await corpusFetchArtifact('_run', 'manifest');
  if (!state.manifest) {
    corpusSetStatus('This run has no manifest; it may have been cleaned up.', 'error');
    return;
  }

  const cohortSelect = document.getElementById('corpusCohortSelect');
  cohortSelect.innerHTML = '';
  state.manifest.cohorts.forEach(function (cohort) {
    const option = document.createElement('option');
    option.value = cohort.slug;
    option.textContent = cohort.label + ' (' + cohort.manuscripts + ' manuscripts)';
    cohortSelect.appendChild(option);
  });

  state.cohort = state.manifest.cohorts[0] ? state.manifest.cohorts[0].slug : null;
  cohortSelect.value = state.cohort;
  // A run over a hand-picked corpus is not comparable with one over the whole of
  // it - every rarity weight differs - so the page has to say which it is showing.
  const picked = (state.run.params || {}).manuscript_uuids;
  corpusSetStatus(picked && picked.length
    ? 'This run was limited to ' + picked.length + ' hand-picked manuscripts.'
    : '');
  await corpusRenderActiveTab(true);
}

function corpusStartPolling(uuid) {
  const state = corpusAnalysisState;
  if (state.pollTimer) clearInterval(state.pollTimer);
  state.pollTimer = setInterval(async function () {
    const response = await fetch(pageRoot + '/analysis/runs/' + uuid + '/',
      { credentials: 'include' });
    if (!response.ok) return;
    const run = await response.json();
    corpusShowProgress(run);
    if (run.status === 'done' || run.status === 'failed') {
      clearInterval(state.pollTimer);
      state.pollTimer = null;
      state.cache = {};
      await corpusLoadRuns(uuid);
    }
  }, 2500);
}

/* ---------------------------------------------------------------- *
 * Tabs
 * ---------------------------------------------------------------- */

const CORPUS_TABS = ['report', 'prayers3d', 'heatmap', 'map', 'seriation', 'layers'];

function corpusActivateTab(tab) {
  corpusAnalysisState.activeTab = tab;
  CORPUS_TABS.forEach(function (name) {
    const panel = document.getElementById('corpusTab-' + name);
    const button = document.getElementById('corpusTabButton-' + name);
    if (panel) panel.style.display = name === tab ? 'block' : 'none';
    if (button) {
      button.className = 'py-1 px-4 rounded font-semibold text-sm drop-shadow ' +
        (name === tab
          ? 'bg-[#795a42] text-white'
          : 'bg-[#efe6de] text-[#0d1b2a] hover:bg-[#e3d5ca]');
    }
  });
  document.getElementById('corpusMetricWrapper').style.display =
    tab === 'heatmap' ? 'flex' : 'none';
  document.getElementById('corpusColorWrapper').style.display =
    tab === 'map' ? 'flex' : 'none';

  return corpusRenderActiveTab(false);
}

/**
 * Wait for the prayer map iframe to have drawn at least one frame.
 *
 * It is a separate document running its own three.js loop, so neither the tab
 * render nor the iframe load event tells us the WebGL buffer holds anything yet.
 */
function corpusPrayerFrameReady() {
  const frame = document.getElementById('corpusPrayerFrame');
  if (!frame || !frame.getAttribute('src')) return Promise.resolve();

  return new Promise(function (resolve) {
    let settled = false;
    const settle = function () {
      if (settled) return;
      settled = true;
      // The scene is built after load and drawn on the following frames.
      setTimeout(resolve, 1500);
    };
    let ready = false;
    try {
      ready = !!frame.contentDocument && frame.contentDocument.readyState === 'complete';
    } catch (err) {
      ready = false;
    }
    if (ready) settle();
    else frame.addEventListener('load', settle, { once: true });
    setTimeout(settle, 10000);
  });
}

/**
 * Render every tab, not just the one on screen.
 *
 * Tabs are rendered lazily, and a hidden panel has no width, so a chart drawn
 * into one would come out zero-sized. Each tab is therefore really opened, drawn
 * and awaited in turn, then the tab the reader was on is restored.
 */
async function corpusRenderEveryTab() {
  const original = corpusAnalysisState.activeTab;
  for (let i = 0; i < CORPUS_TABS.length; i++) {
    const tab = CORPUS_TABS[i];
    try {
      await corpusActivateTab(tab);
      if (tab === 'prayers3d') await corpusPrayerFrameReady();
    } catch (err) {
      // One tab failing to draw must not cost us the rest of the printout.
    }
  }
  await corpusActivateTab(original);
}

async function corpusRenderActiveTab(force) {
  const state = corpusAnalysisState;
  if (!state.run || !state.cohort) return;

  const tab = state.activeTab;
  if (tab === 'report') return corpusRenderReport();
  if (tab === 'prayers3d') return corpusRenderPrayerMap(force);
  if (tab === 'heatmap') return corpusRenderHeatmap();
  if (tab === 'map') return corpusRenderMap();
  if (tab === 'seriation') return corpusRenderSeriation();
  if (tab === 'layers') return corpusRenderLayers();
}

async function corpusRenderReport() {
  const report = await corpusFetchArtifact(corpusAnalysisState.cohort, 'report');
  CorpusAnalysisViz.renderReport('#corpusReport', report);
}

function corpusRenderPrayerMap(force) {
  const state = corpusAnalysisState;
  const frame = document.getElementById('corpusPrayerFrame');
  const url = '/static/corpus_3d/index.html?run=' + encodeURIComponent(state.run.uuid) +
    '&cohort=' + encodeURIComponent(state.cohort) +
    '&api=' + encodeURIComponent(pageRoot);
  if (force || frame.dataset.loaded !== url) {
    frame.src = url;
    frame.dataset.loaded = url;
  }
}

async function corpusRenderHeatmap() {
  const state = corpusAnalysisState;
  const [manuscripts, matrices, clusters] = await Promise.all([
    corpusFetchArtifact(state.cohort, 'manuscripts'),
    corpusFetchArtifact(state.cohort, 'matrices'),
    corpusFetchArtifact(state.cohort, 'ms_clusters')
  ]);
  if (!manuscripts || !matrices) {
    return CorpusAnalysisViz.message('#corpusHeatmap', 'No matrices in this comparison group.');
  }

  const metricSelect = document.getElementById('corpusMetricSelect');
  if (!metricSelect.options.length) {
    Object.keys(matrices.metrics).forEach(function (metric) {
      const option = document.createElement('option');
      option.value = metric;
      option.textContent = metric.replace(/_/g, ' ');
      metricSelect.appendChild(option);
    });
    metricSelect.value = matrices.primary || state.metric;
    state.metric = metricSelect.value;
  }

  CorpusAnalysisViz.renderHeatmap({
    selector: '#corpusHeatmap',
    manuscripts: manuscripts.manuscripts,
    matrices: matrices,
    clusters: clusters || {},
    metric: state.metric,
    onSelectPair: function (a, b) {
      CorpusAnalysisViz.renderPairDetail('#corpusPairDetail', {
        a: a, b: b,
        manuscripts: manuscripts.manuscripts,
        matrices: matrices,
        compareUrl: '/static/page.html?p=ms_formulas_graph'
          + '&left=' + encodeURIComponent(manuscripts.manuscripts[a].uuid)
          + '&right=' + encodeURIComponent(manuscripts.manuscripts[b].uuid)
          + '&leftLabel=' + encodeURIComponent(manuscripts.manuscripts[a].label)
          + '&rightLabel=' + encodeURIComponent(manuscripts.manuscripts[b].label)
      });
    }
  });
}

async function corpusRenderMap() {
  const state = corpusAnalysisState;
  const [manuscripts, embedding, clusters] = await Promise.all([
    corpusFetchArtifact(state.cohort, 'manuscripts'),
    corpusFetchArtifact(state.cohort, 'ms_embedding'),
    corpusFetchArtifact(state.cohort, 'ms_clusters')
  ]);
  if (!manuscripts || !embedding) {
    return CorpusAnalysisViz.message('#corpusMap', 'No embedding in this comparison group.');
  }
  CorpusAnalysisViz.renderMdsMap({
    selector: '#corpusMap',
    manuscripts: manuscripts.manuscripts,
    embedding: embedding,
    clusters: clusters || {},
    colorBy: state.colorBy
  });
}

async function corpusRenderSeriation() {
  const presence = await corpusFetchArtifact(corpusAnalysisState.cohort, 'presence');
  if (!presence) {
    return CorpusAnalysisViz.message('#corpusSeriation', 'No presence matrix in this comparison group.');
  }
  CorpusAnalysisViz.renderSeriation({ selector: '#corpusSeriation', presence: presence });
}

async function corpusRenderLayers() {
  const layers = await corpusFetchArtifact(corpusAnalysisState.cohort, 'layers');
  CorpusAnalysisViz.renderLayers({ selector: '#corpusLayers', layers: layers });
  CorpusAnalysisViz.renderLayerTable('#corpusLayerTable', layers);
}

/* ---------------------------------------------------------------- *
 * Choosing the manuscripts
 * ---------------------------------------------------------------- */

function corpusMinItems() {
  return parseInt(document.getElementById('corpusMinItems').value, 10) || 20;
}

/**
 * The chosen manuscripts, or null when the whole corpus is in play.
 *
 * Null and "every box ticked" mean the same run, but not the same request: sending
 * no list lets the run take whatever is in the catalogue when it starts, which is
 * what someone who never opened the picker expects.
 */
function corpusSelectedManuscripts() {
  const selection = corpusAnalysisState.selection;
  if (!selection.loaded) return null;
  if (selection.chosen.size === selection.manuscripts.length) return null;
  return selection.manuscripts.filter(function (ms) {
    return selection.chosen.has(ms.uuid);
  });
}

async function corpusLoadManuscriptChoices() {
  const selection = corpusAnalysisState.selection;
  if (selection.loaded) return true;

  const response = await fetch(pageRoot + '/analysis/manuscripts/', { credentials: 'include' });
  if (!response.ok) {
    corpusSetStatus('Could not load the list of manuscripts.', 'error');
    return false;
  }
  const data = await response.json();
  selection.manuscripts = data.manuscripts || [];
  selection.genres = data.genres || [];
  // Everything to begin with: the picker narrows a corpus, it does not build one
  // from nothing, and an empty panel would read as "nothing to analyse".
  selection.chosen = new Set(selection.manuscripts.map(function (ms) { return ms.uuid; }));
  selection.loaded = true;

  corpusRenderGenreChips();
  corpusRenderManuscriptList();
  corpusSyncSelection();
  return true;
}

function corpusGenreMembers(genreUuid) {
  return corpusAnalysisState.selection.manuscripts.filter(function (ms) {
    return genreUuid === CORPUS_UNGROUPED
      ? !ms.genres.length : ms.genres.indexOf(genreUuid) !== -1;
  });
}

function corpusRenderGenreChips() {
  const selection = corpusAnalysisState.selection;
  const node = document.getElementById('corpusMsGenres');
  const groups = selection.genres.slice();

  // Manuscripts under no genre form a group of their own, or they would be the
  // only ones the bulk controls could not reach.
  const ungrouped = corpusGenreMembers(CORPUS_UNGROUPED).length;
  if (ungrouped) {
    groups.push({ uuid: CORPUS_UNGROUPED, title: 'No genre recorded', manuscripts: ungrouped });
  }
  if (!groups.length) return (node.innerHTML = '');

  node.innerHTML = '<span class="text-sm text-gray-600 self-center mr-1">By genre:</span>' +
    groups.map(function (genre) {
      return '<button type="button" class="corpus-genre-chip py-1 px-3 rounded text-sm ' +
        'font-semibold border" data-genre="' + corpusEscapeHtml(genre.uuid) + '">' +
        corpusEscapeHtml(genre.title) + ' (' + genre.manuscripts + ')</button>';
    }).join('');

  node.querySelectorAll('.corpus-genre-chip').forEach(function (chip) {
    chip.addEventListener('click', function () {
      corpusToggleGenre(chip.dataset.genre);
    });
  });
}

function corpusToggleGenre(genreUuid) {
  const chosen = corpusAnalysisState.selection.chosen;
  const members = corpusGenreMembers(genreUuid);
  const allIn = members.every(function (ms) { return chosen.has(ms.uuid); });
  members.forEach(function (ms) {
    if (allIn) chosen.delete(ms.uuid);
    else chosen.add(ms.uuid);
  });
  corpusSyncSelection();
}

function corpusManuscriptMatchesFilter(ms, filter) {
  if (!filter) return true;
  return (ms.label + ' ' + ms.shelf_mark).toLowerCase().indexOf(filter) !== -1;
}

function corpusRenderManuscriptList() {
  const selection = corpusAnalysisState.selection;
  const node = document.getElementById('corpusMsList');
  const titles = {};
  selection.genres.forEach(function (genre) { titles[genre.uuid] = genre.title; });

  const visible = selection.manuscripts.filter(function (ms) {
    return corpusManuscriptMatchesFilter(ms, selection.filter);
  });

  if (!visible.length) {
    node.innerHTML = '<p class="text-sm text-gray-600 py-2">No manuscript matches that filter.</p>';
    return;
  }

  // Built as one string and wired with a single delegated listener: the corpus
  // can reach several hundred rows, and a listener each would be that many.
  node.innerHTML = visible.map(function (ms) {
    const dated = ms.year_from ? ms.year_from + '–' + (ms.year_to || ms.year_from) : '';
    const genres = ms.genres.map(function (uuid) { return titles[uuid] || uuid; }).join(', ');
    const facts = [
      ms.n_items + ' items',
      ms.n_distinct + ' distinct formulas',
      dated,
      genres,
    ].filter(Boolean).join(' · ');

    return '<label class="corpus-ms-row flex items-start gap-2 py-1 px-1 rounded ' +
      'hover:bg-[#fef9f6] cursor-pointer" data-uuid="' + corpusEscapeHtml(ms.uuid) + '">' +
      '<input type="checkbox" class="mt-1" data-uuid="' + corpusEscapeHtml(ms.uuid) + '">' +
      '<span class="flex-1">' +
      '<span class="font-semibold">' + corpusEscapeHtml(ms.label) + '</span>' +
      '<span class="block text-xs text-gray-600">' + corpusEscapeHtml(facts) + '</span>' +
      '<span class="corpus-ms-thin block text-xs text-amber-700" style="display:none">' +
      'Below the minimum item count — this run would set it aside.</span>' +
      '</span></label>';
  }).join('');

  node.onchange = function (event) {
    const input = event.target;
    if (!input || input.type !== 'checkbox') return;
    const chosen = selection.chosen;
    if (input.checked) chosen.add(input.dataset.uuid);
    else chosen.delete(input.dataset.uuid);
    corpusSyncSelection();
  };
}

/**
 * Push the selection back onto everything that displays it.
 *
 * One function rather than a re-render, so ticking a box neither rebuilds several
 * hundred rows nor throws away the reader's scroll position.
 */
function corpusSyncSelection() {
  const selection = corpusAnalysisState.selection;
  const chosen = selection.chosen;
  const minItems = corpusMinItems();
  const byUuid = {};
  selection.manuscripts.forEach(function (ms) { byUuid[ms.uuid] = ms; });

  document.querySelectorAll('#corpusMsList input[type="checkbox"]').forEach(function (input) {
    input.checked = chosen.has(input.dataset.uuid);
  });
  document.querySelectorAll('#corpusMsList .corpus-ms-row').forEach(function (row) {
    const ms = byUuid[row.dataset.uuid];
    const thin = row.querySelector('.corpus-ms-thin');
    // Only worth flagging on a manuscript the reader has actually asked for.
    const show = ms && ms.n_items < minItems && chosen.has(ms.uuid);
    if (thin) thin.style.display = show ? 'block' : 'none';
  });

  document.querySelectorAll('.corpus-genre-chip').forEach(function (chip) {
    const members = corpusGenreMembers(chip.dataset.genre);
    const inside = members.filter(function (ms) { return chosen.has(ms.uuid); }).length;
    const base = 'corpus-genre-chip py-1 px-3 rounded text-sm font-semibold border ';
    if (!inside) chip.className = base + 'bg-white border-[#e3d5ca] text-[#0d1b2a]';
    else if (inside === members.length) chip.className = base + 'bg-[#795a42] border-[#795a42] text-white';
    else chip.className = base + 'bg-[#efe6de] border-[#795a42] text-[#0d1b2a]';
  });

  const total = selection.manuscripts.length;
  const picked = selection.manuscripts.filter(function (ms) { return chosen.has(ms.uuid); });
  const comparable = picked.filter(function (ms) { return ms.n_items >= minItems; });

  const toggle = document.getElementById('corpusSelectionToggle');
  if (toggle) {
    toggle.textContent = 'Manuscripts: ' +
      (picked.length === total ? 'all (' + total + ')' : picked.length + ' of ' + total);
  }

  const summary = document.getElementById('corpusMsSummary');
  if (summary) {
    const skipped = picked.length - comparable.length;
    let text = picked.length + ' of ' + total + ' manuscripts selected; ' +
      comparable.length + ' reach the minimum of ' + minItems + ' items and would be compared';
    text += skipped ? ', ' + skipped + ' would be set aside as too thinly indexed.' : '.';
    if (comparable.length < 2) {
      text += ' At least two are needed to compare anything.';
    }
    summary.textContent = text;
    summary.className = 'text-sm mt-2 ' +
      (comparable.length < 2 ? 'text-red-600' : 'text-gray-600');
  }
}

async function corpusToggleSelectionPanel() {
  const panel = document.getElementById('corpusSelectionPanel');
  const opening = panel.style.display === 'none';
  if (opening && !(await corpusLoadManuscriptChoices())) return;
  panel.style.display = opening ? 'block' : 'none';
}

function corpusSetAllManuscripts(mode) {
  const selection = corpusAnalysisState.selection;
  const chosen = selection.chosen;
  // The bulk buttons act on what the filter is showing, so "select all" during a
  // search means the search, not the catalogue.
  selection.manuscripts
    .filter(function (ms) { return corpusManuscriptMatchesFilter(ms, selection.filter); })
    .forEach(function (ms) {
      if (mode === 'all') chosen.add(ms.uuid);
      else if (mode === 'none') chosen.delete(ms.uuid);
      else if (chosen.has(ms.uuid)) chosen.delete(ms.uuid);
      else chosen.add(ms.uuid);
    });
  corpusSyncSelection();
}

/* ---------------------------------------------------------------- *
 * Starting a run
 * ---------------------------------------------------------------- */

async function corpusStartRun() {
  const state = corpusAnalysisState;
  const minItems = corpusMinItems();

  const body = { min_items: minItems };
  const selection = corpusSelectedManuscripts();
  if (selection) {
    const comparable = selection.filter(function (ms) { return ms.n_items >= minItems; });
    if (comparable.length < 2) {
      return corpusSetStatus(
        'At least two of the selected manuscripts must reach the minimum item count; ' +
        comparable.length + ' currently do. Widen the selection or lower the threshold.',
        'error');
    }
    body.manuscript_uuids = selection.map(function (ms) { return ms.uuid; });
  } else if (state.selection.loaded && !state.selection.chosen.size) {
    return corpusSetStatus('No manuscript is selected.', 'error');
  }

  corpusSetStatus('Starting…');

  const response = await fetch(pageRoot + '/analysis/runs/start/', {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body)
  });
  const data = await response.json().catch(function () { return {}; });

  if (!response.ok) {
    return corpusSetStatus(data.detail || 'Could not start the run.', 'error');
  }
  corpusSetStatus(data.detail || 'Run started.');
  // The selection is now the run's, not a pending choice; leaving the panel open
  // would invite editing something that has already been dispatched.
  document.getElementById('corpusSelectionPanel').style.display = 'none';
  corpusAnalysisState.cache = {};
  await corpusLoadRuns(data.run && data.run.uuid);
  if (data.run && data.queued) corpusStartPolling(data.run.uuid);
}

/* ---------------------------------------------------------------- *
 * Printing
 * ---------------------------------------------------------------- */

/**
 * Print whatever is on screen right now.
 *
 * Works the same way as printDiv() on the manuscript page: collect .printIt
 * elements and write them into a new window with printed.css. Because it takes the
 * live DOM, the zoom, the chosen metric and the open tab print exactly as the
 * reader arranged them. Canvases have to be turned into images first — their
 * pixels do not travel with outerHTML.
 */
function corpusCanvasDataUrl(canvas) {
  try {
    return canvas.toDataURL('image/png');
  } catch (err) {
    // A canvas that ever drew a cross-origin image is tainted and refuses to
    // export. Nothing to do about it here beyond leaving a gap in the printout.
    return null;
  }
}

/**
 * Serialize what is on screen into printable HTML.
 *
 * Every node is created in *this* document. An earlier version built the
 * replacement <img> with printWindow.document.createElement and inserted it into
 * a clone owned by this document; that cross-document insertion is what made the
 * whole print path fail the moment the print window stopped being reachable.
 */
function corpusImageTag(source) {
  return '<img style="max-width:100%" src="' + source + '">';
}

/**
 * Snapshot of the prayer map, which lives in its own iframe.
 *
 * Its canvas is WebGL, so it only reads back because the renderer is created
 * with preserveDrawingBuffer (see static/corpus_3d/index.html); without that the
 * buffer is already cleared by the time we ask for it.
 */
function corpusPrayerFrameSnapshot() {
  const frame = document.getElementById('corpusPrayerFrame');
  if (!frame) return null;

  let canvas = null;
  try {
    canvas = frame.contentDocument && frame.contentDocument.querySelector('canvas');
  } catch (err) {
    return null;
  }
  if (!canvas) return null;

  const source = corpusCanvasDataUrl(canvas);
  return source ? corpusImageTag(source) : null;
}

/**
 * Make an SVG scale down to the printed page.
 *
 * d3 sizes these to the on-screen container with width/height attributes and no
 * viewBox. `max-width:100%` then shrinks the box but not the coordinate system,
 * so the chart simply got cut off at the page edge. Giving it a viewBox built
 * from those attributes is what makes it scale instead of clip - and the legend,
 * which every renderer draws inside the same <svg>, scales along with it.
 */
function corpusScaleSvg(svg) {
  if (svg.getAttribute('viewBox')) return;

  const width = parseFloat(svg.getAttribute('width'));
  const height = parseFloat(svg.getAttribute('height'));
  if (!isFinite(width) || !isFinite(height) || width <= 0 || height <= 0) return;

  svg.setAttribute('viewBox', '0 0 ' + width + ' ' + height);
  svg.setAttribute('preserveAspectRatio', 'xMidYMid meet');
  svg.removeAttribute('width');
  svg.removeAttribute('height');
  svg.style.width = '100%';
  svg.style.height = 'auto';
}

function corpusElementToPrintable(element) {
  if (element.tagName === 'CANVAS') {
    const source = corpusCanvasDataUrl(element);
    return source
      ? corpusImageTag(source)
      : '<p><em>Canvas could not be captured for printing.</em></p>';
  }

  const clone = element.cloneNode(true);

  // Canvas pixels do not travel with outerHTML, so each one is swapped for a
  // snapshot taken from the live element it was cloned from.
  const canvases = element.querySelectorAll('canvas');
  clone.querySelectorAll('canvas').forEach(function (node, index) {
    const image = document.createElement('img');
    const source = canvases[index] ? corpusCanvasDataUrl(canvases[index]) : null;
    if (source) {
      image.src = source;
    } else {
      image.alt = 'canvas';
    }
    image.style.maxWidth = '100%';
    node.parentNode.replaceChild(image, node);
  });

  if (clone.tagName === 'SVG' || clone.tagName === 'svg') corpusScaleSvg(clone);
  clone.querySelectorAll('svg').forEach(corpusScaleSvg);

  const html = clone.outerHTML;
  // Keep a figure and its legend from being split across two pages.
  return (clone.querySelector && (clone.querySelector('svg') || clone.querySelector('img')))
      || clone.tagName === 'SVG' || clone.tagName === 'svg'
    ? '<div class="corpus-figure">' + html + '</div>'
    : html;
}

/**
 * Serialize every tab into printable HTML, one section per tab.
 *
 * Every node is created in *this* document. An earlier version built the
 * replacement <img> with printWindow.document.createElement and inserted it into
 * a clone owned by this document; that cross-document insertion is what made the
 * whole print path fail.
 */
function corpusPrintableSections() {
  const sections = [];

  CORPUS_TABS.forEach(function (tab) {
    const panel = document.getElementById('corpusTab-' + tab);
    if (!panel) return;

    const collected = [];
    panel.querySelectorAll('.printIt').forEach(function (element) {
      if (element.closest('.corpus-print-skip')) return;
      // Only the outermost marked element: a nested one would print twice.
      if (element.parentElement && element.parentElement.closest('.printIt')) return;
      collected.push(corpusElementToPrintable(element));
    });

    if (tab === 'prayers3d') {
      const snapshot = corpusPrayerFrameSnapshot();
      if (snapshot) collected.push('<div class="corpus-figure">' + snapshot + '</div>');
    }

    if (!collected.length) return;

    const button = document.getElementById('corpusTabButton-' + tab);
    sections.push({
      tab: tab,
      heading: corpusEscapeHtml(button ? button.textContent.trim() : tab),
      html: collected.join('\n')
    });
  });

  return sections;
}

function corpusEscapeHtml(text) {
  const holder = document.createElement('span');
  holder.textContent = text == null ? '' : String(text);
  return holder.innerHTML;
}

function corpusPrintDocument(title) {
  const state = corpusAnalysisState;
  const cohort = state.manifest && state.manifest.cohorts.find(function (c) {
    return c.slug === state.cohort;
  });

  let heading = '<h1>Corpus analysis</h1>';
  if (cohort) {
    heading += '<p>' + corpusEscapeHtml(cohort.label) + ' — ' + cohort.manuscripts +
      ' manuscripts, ' + cohort.formulas + ' formulas. Run ' +
      corpusEscapeHtml(state.run.uuid) + ', ' +
      corpusEscapeHtml(new Date(state.run.created_at).toLocaleString()) + '.</p>';
  }

  // The charts are all far wider than they are tall, so they get landscape
  // pages of their own; only the report is set portrait. Named pages need the
  // section to be the element that starts the page, hence break-before here.
  const style = '' +
    '@page { size: A4 portrait; margin: 14mm; }' +
    '@page chartpage { size: A4 landscape; margin: 10mm; }' +
    '.corpus-section { break-before: page; page-break-before: always; }' +
    '.corpus-section:first-of-type { break-before: auto; page-break-before: auto; }' +
    '.corpus-section-chart { page: chartpage; }' +
    '.corpus-figure { break-inside: avoid; page-break-inside: avoid; margin: 0 0 8pt; }' +
    '.corpus-figure svg, .corpus-figure img '
      + '{ max-width: 100%; max-height: 160mm; height: auto; object-fit: contain; }' +
    'svg, img { max-width: 100%; height: auto; }' +
    'table { border-collapse: collapse; width: 100%; font-size: 9pt; }' +
    'td, th { padding: 2px 6px; text-align: left; vertical-align: top; }' +
    'h2 { margin: 0 0 6pt; }';

  const body = corpusPrintableSections().map(function (section) {
    const chart = section.tab !== 'report';
    return '<section class="corpus-section' + (chart ? ' corpus-section-chart' : '') + '">'
      + '<h2>' + section.heading + '</h2>' + section.html + '</section>';
  }).join('\n');

  return '<!DOCTYPE html><html><head><meta charset="utf-8">'
    + '<title>' + corpusEscapeHtml(title || 'Corpus analysis') + '</title>'
    + '<link rel="stylesheet" href="/static/css/printed.css" />'
    + '<style>' + style + '</style>'
    + '</head><body data-corpus-print="ready">'
    + '<section class="corpus-section">' + heading + '</section>'
    + body + '</body></html>';
}

/**
 * Print whatever is on screen right now.
 *
 * Rendered into a hidden same-document iframe rather than a popup. A popup is
 * its own browsing context: it can be blocked, it can be handed back an existing
 * window of the same name, and any DOM work across the boundary is subject to
 * the same-origin check — which is how this used to die with "Blocked a frame
 * ... from accessing a cross-origin frame" on printWindow.print(). A srcdoc
 * iframe is same-origin with this page by construction, so none of that applies.
 *
 * Because it takes the live DOM, the zoom, the chosen metric and the open tab
 * print exactly as the reader arranged them.
 */
async function printCorpusAnalysis(title) {
  const previous = document.getElementById('corpusPrintFrame');
  if (previous) previous.remove();

  // The charts live in tabs that are drawn only when opened, so without this the
  // printout would carry whichever single tab happened to be on screen.
  corpusSetStatus('Drawing every tab for the printout…');
  let renderFailed = false;
  try {
    await corpusRenderEveryTab();
  } catch (err) {
    renderFailed = true;
  }
  corpusSetStatus(
    renderFailed ? 'Some tabs could not be drawn; printing what is available.' : '',
    renderFailed ? 'error' : null
  );

  const frame = document.createElement('iframe');
  frame.id = 'corpusPrintFrame';
  frame.setAttribute('aria-hidden', 'true');
  frame.setAttribute('title', 'Print preview');
  // Parked off-screen at a real page size rather than hidden. A frame that is
  // display:none, visibility:hidden or 0x0 is never laid out, and Chrome prints
  // exactly what it laid out - which is why hiding it that way yields blank pages.
  frame.style.cssText =
    'position:fixed;left:-10000px;top:0;width:794px;height:1123px;border:0;';

  // onload fires once the iframe document and its subresources (printed.css and
  // every canvas snapshot) are in, so there is nothing left to guess a delay for.
  frame.onload = function () {
    const frameWindow = frame.contentWindow;
    if (!frameWindow) {
      frame.remove();
      return corpusSetStatus('The print view could not be prepared.', 'error');
    }
    // Attaching an iframe to the document fires a load event for the empty
    // about:blank it starts life with, before srcdoc has been parsed. Printing
    // on that one is what produced blank pages, so wait for our own document.
    const body = frameWindow.document.body;
    if (!body || body.dataset.corpusPrint !== 'ready') return;

    let removed = false;
    const cleanup = function () {
      if (removed) return;
      removed = true;
      frame.remove();
    };

    frameWindow.onafterprint = cleanup;
    // Safari never fires onafterprint for an iframe; drop it after a grace period.
    setTimeout(cleanup, 60000);

    try {
      frameWindow.focus();
      frameWindow.print();
    } catch (err) {
      cleanup();
      corpusSetStatus('The browser refused to open the print dialog.', 'error');
    }
  };

  // srcdoc first, then insert: an iframe only starts loading once it is
  // connected, so this way the single load event is the one that matters.
  frame.srcdoc = corpusPrintDocument(title);
  document.body.appendChild(frame);
  return true;
}

/* ---------------------------------------------------------------- *
 * Init
 * ---------------------------------------------------------------- */

function corpus_analysis_init() {
  const state = corpusAnalysisState;
  state.cache = {};

  // Prayer references resolve themselves on hover, one batched request at a
  // time, so a reader can see what a CO number actually is without the page
  // loading anything it might not need.
  if (window.PrayerHover) {
    PrayerHover.init({ endpoint: pageRoot + '/analysis/formulas/' });
  }

  document.getElementById('corpusRunSelect').addEventListener('change', async function (e) {
    state.cache = {};
    await corpusSelectRun(e.target.value);
  });
  document.getElementById('corpusCohortSelect').addEventListener('change', function (e) {
    state.cohort = e.target.value;
    document.getElementById('corpusMetricSelect').innerHTML = '';
    corpusRenderActiveTab(true);
  });
  document.getElementById('corpusMetricSelect').addEventListener('change', function (e) {
    state.metric = e.target.value;
    corpusRenderHeatmap();
  });
  document.getElementById('corpusColorSelect').addEventListener('change', function (e) {
    state.colorBy = e.target.value;
    corpusRenderMap();
  });
  CORPUS_TABS.forEach(function (tab) {
    const button = document.getElementById('corpusTabButton-' + tab);
    if (button) button.addEventListener('click', function () { corpusActivateTab(tab); });
  });
  const startButton = document.getElementById('corpusStartButton');
  if (startButton) startButton.addEventListener('click', corpusStartRun);

  document.getElementById('corpusSelectionToggle')
    .addEventListener('click', corpusToggleSelectionPanel);
  document.getElementById('corpusMsAll')
    .addEventListener('click', function () { corpusSetAllManuscripts('all'); });
  document.getElementById('corpusMsNone')
    .addEventListener('click', function () { corpusSetAllManuscripts('none'); });
  document.getElementById('corpusMsInvert')
    .addEventListener('click', function () { corpusSetAllManuscripts('invert'); });
  document.getElementById('corpusMsSearch').addEventListener('input', function (e) {
    state.selection.filter = e.target.value.trim().toLowerCase();
    corpusRenderManuscriptList();
    corpusSyncSelection();
  });
  // The threshold decides which of the chosen manuscripts are thick enough to
  // compare, so the panel has to answer to it as it is typed.
  document.getElementById('corpusMinItems').addEventListener('input', function () {
    if (state.selection.loaded) corpusSyncSelection();
  });

  window.addEventListener('resize', function () {
    if (['heatmap', 'map', 'seriation', 'layers'].indexOf(state.activeTab) !== -1) {
      corpusRenderActiveTab(false);
    }
  });

  corpusActivateTab('report');
  corpusLoadRuns();
}
