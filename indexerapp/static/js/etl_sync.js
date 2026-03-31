let etlOverview = null;
let etlSelectedPeerId = null;
let etlManuscriptsTable = null;
let etlPeerManuscripts = [];

async function etl_sync_init() {
    bindETLSyncEvents();
    appendETLLog('Loading ETL overview...');
    await loadETLOverview();
}

function bindETLSyncEvents() {
    const refreshButton = document.getElementById('etl-refresh-overview');
    if (refreshButton) {
        refreshButton.addEventListener('click', async () => {
            appendETLLog('Refreshing ETL overview...');
            await loadETLOverview();
        });
    }

    const peerSelect = document.getElementById('etl-peer-select');
    if (peerSelect) {
        peerSelect.addEventListener('change', (event) => {
            etlSelectedPeerId = event.target.value || null;
            renderSelectedPeerStatus();
        });
    }

    document.querySelectorAll('.etl-sync-category').forEach((button) => {
        button.addEventListener('click', async () => {
            const category = button.dataset.category;
            await triggerCategoryPull(category);
        });
    });

    const loadManuscriptsButton = document.getElementById('etl-load-manuscripts');
    if (loadManuscriptsButton) {
        loadManuscriptsButton.addEventListener('click', async () => {
            await loadPeerManuscripts();
        });
    }
}

async function loadETLOverview() {
    try {
        const payload = await etlFetchJson('/api/etl/ui/overview/');
        etlOverview = payload;
        renderLocalSummary();
        renderPeerOptions();
        renderSelectedPeerStatus();
        appendETLLog('ETL overview loaded.');
    } catch (error) {
        appendETLLog(`Overview error: ${error.message}`);
    }
}

function renderLocalSummary() {
    const container = document.getElementById('etl-local-summary');
    if (!container) {
        return;
    }

    const local = (etlOverview && etlOverview.local) || {};
    const counts = local.model_category_counts || {};
    const cards = [
        ['Site', local.site_name || 'Unknown'],
        ['Role', local.role || 'undefined'],
        ['Peer count', String((etlOverview && etlOverview.peers ? etlOverview.peers.length : 0))],
        ['Categories', Object.entries(counts).map(([key, value]) => `${key}: ${value}`).join(', ') || 'No data'],
    ];

    container.innerHTML = cards.map(([label, value]) => `
        <div class="bg-white border border-[#eadfd6] rounded p-3">
            <div class="text-xs uppercase tracking-[0.18em] text-[#8a6d55] mb-1">${escapeHtml(label)}</div>
            <div class="text-sm text-[#0d1b2a] font-semibold break-words">${escapeHtml(value)}</div>
        </div>
    `).join('');
}

function renderPeerOptions() {
    const select = document.getElementById('etl-peer-select');
    if (!select) {
        return;
    }

    const peers = (etlOverview && etlOverview.peers) || [];
    select.innerHTML = '';

    if (!peers.length) {
        select.innerHTML = '<option value="">No configured peers</option>';
        etlSelectedPeerId = null;
        return;
    }

    peers.forEach((peer, index) => {
        const option = document.createElement('option');
        option.value = peer.id;
        option.textContent = `${peer.label} (${peer.url})`;
        if ((!etlSelectedPeerId && index === 0) || etlSelectedPeerId === peer.id) {
            option.selected = true;
            etlSelectedPeerId = peer.id;
        }
        select.appendChild(option);
    });
}

function renderSelectedPeerStatus() {
    const container = document.getElementById('etl-peer-status');
    if (!container) {
        return;
    }

    const peer = getSelectedPeer();
    if (!peer) {
        container.innerHTML = '<span class="text-[#8b0000]">No peer selected.</span>';
        return;
    }

    if (!peer.reachable) {
        container.innerHTML = `
            <div class="text-[#8b0000] font-semibold">Connection failed</div>
            <div class="mt-1">${escapeHtml(peer.error || 'Unknown peer error.')}</div>
        `;
        return;
    }

    const status = peer.status || {};
    const categoryCounts = status.model_category_counts || {};
    container.innerHTML = `
        <div class="font-semibold text-[#0d1b2a]">${escapeHtml(status.site_name || peer.label)} (${escapeHtml(status.role || 'undefined')})</div>
        <div class="mt-1">${escapeHtml(peer.url)}</div>
        <div class="mt-1 text-[#3d4b5c]">${escapeHtml(Object.entries(categoryCounts).map(([key, value]) => `${key}: ${value}`).join(', ') || 'No category counts.')}</div>
    `;
}

async function triggerCategoryPull(category) {
    const peer = getSelectedPeer();
    if (!peer) {
        appendETLLog('Select a peer before starting synchronization.');
        return;
    }

    const sinceValue = (document.getElementById('etl-since') || {}).value || '';
    appendETLLog(`Pulling ${category} from ${peer.url}${sinceValue ? ` since ${sinceValue}` : ''}...`);

    try {
        const payload = await etlFetchJson('/api/etl/ui/pull-category/', {
            method: 'POST',
            body: JSON.stringify({
                peer: peer.id,
                category: category,
                since: sinceValue,
            }),
        });

        const result = payload.result || {};
        const importSummary = result.import_summary || {};
        const deleteSummary = result.delete_summary || {};
        appendETLLog(
            `${category} pull completed: created=${importSummary.created || 0}, updated=${importSummary.updated || 0}, skipped=${importSummary.skipped || 0}, deleted=${deleteSummary.deleted || 0}, missing_deleted=${deleteSummary.missing || 0}.`
        );
    } catch (error) {
        appendETLLog(`${category} pull failed: ${error.message}`);
    }
}

async function loadPeerManuscripts() {
    const peer = getSelectedPeer();
    if (!peer) {
        appendETLLog('Select a peer before loading manuscript packages.');
        return;
    }

    appendETLLog(`Loading manuscript packages from ${peer.url}...`);
    try {
        const payload = await etlFetchJson(`/api/etl/ui/manuscripts/?peer=${encodeURIComponent(peer.id)}`);
        etlPeerManuscripts = ((payload.payload || {}).results || []);
        renderPeerManuscriptsTable();
        appendETLLog(`Loaded ${etlPeerManuscripts.length} manuscript packages from ${peer.url}.`);
    } catch (error) {
        appendETLLog(`Cannot load manuscript packages: ${error.message}`);
    }
}

function renderPeerManuscriptsTable() {
    const tableElement = $('#etl-manuscripts-table');
    if (!tableElement.length) {
        return;
    }

    if (etlManuscriptsTable) {
        etlManuscriptsTable.destroy();
        $('#etl-manuscripts-table tbody').empty();
    }

    etlManuscriptsTable = tableElement.DataTable({
        data: etlPeerManuscripts,
        columns: [
            {
                data: 'name',
                defaultContent: '',
                render: function(data) {
                    return escapeHtml(data || '');
                }
            },
            {
                data: 'rism_id',
                defaultContent: '',
                render: function(data) {
                    return escapeHtml(data || '');
                }
            },
            {
                data: 'uuid',
                defaultContent: '',
                render: function(data) {
                    return `<span class="text-xs break-all">${escapeHtml(data || '')}</span>`;
                }
            },
            {
                data: 'sync_status',
                defaultContent: '',
                render: function(data) {
                    return escapeHtml(data || '');
                }
            },
            {
                data: 'entry_date',
                defaultContent: '',
                render: function(data) {
                    return escapeHtml(data || '');
                }
            },
            {
                data: null,
                orderable: false,
                searchable: false,
                render: function(data, type, row) {
                    const manuscriptUuid = row.uuid || '';
                    return `<button class="etl-import-manuscript py-1 px-3 text-[#0d1b2a] font-semibold shadow drop-shadow-md bg-[#e8d3c3] rounded hover:bg-[#dec5b2] text-center" data-manuscript-uuid="${escapeAttribute(manuscriptUuid)}">Import</button>`;
                }
            }
        ],
        pageLength: 10,
        destroy: true,
        order: [[0, 'asc']],
    });

    $('#etl-manuscripts-table').off('click', '.etl-import-manuscript');
    $('#etl-manuscripts-table').on('click', '.etl-import-manuscript', async function() {
        const manuscriptUuid = $(this).data('manuscript-uuid');
        await triggerManuscriptPull(manuscriptUuid);
    });
}

async function triggerManuscriptPull(manuscriptUuid) {
    const peer = getSelectedPeer();
    if (!peer || !manuscriptUuid) {
        appendETLLog('Cannot import manuscript package without peer and manuscript UUID.');
        return;
    }

    appendETLLog(`Importing manuscript package ${manuscriptUuid} from ${peer.url}...`);
    try {
        const payload = await etlFetchJson('/api/etl/ui/pull-manuscript/', {
            method: 'POST',
            body: JSON.stringify({
                peer: peer.id,
                manuscript_uuid: manuscriptUuid,
            }),
        });
        const importSummary = (payload.result || {}).import_summary || {};
        appendETLLog(
            `Manuscript import completed: created=${importSummary.created || 0}, updated=${importSummary.updated || 0}, skipped=${importSummary.skipped || 0}.`
        );
    } catch (error) {
        appendETLLog(`Manuscript import failed: ${error.message}`);
    }
}

async function etlFetchJson(url, options = {}) {
    const response = await fetch(url, {
        credentials: 'include',
        headers: {
            'Content-Type': 'application/json',
            ...(options.headers || {}),
        },
        ...options,
    });

    let payload = {};
    try {
        payload = await response.json();
    } catch (error) {
        payload = {};
    }

    if (!response.ok) {
        throw new Error(payload.detail || `HTTP ${response.status}`);
    }

    return payload;
}

function getSelectedPeer() {
    const peers = (etlOverview && etlOverview.peers) || [];
    return peers.find((peer) => peer.id === etlSelectedPeerId) || null;
}

function appendETLLog(message) {
    const container = document.getElementById('etl-log');
    if (!container) {
        return;
    }
    const timestamp = new Date().toISOString().replace('T', ' ').replace('Z', ' UTC');
    const current = container.textContent ? `${container.textContent}\n` : '';
    container.textContent = `${current}[${timestamp}] ${message}`;
    container.scrollTop = container.scrollHeight;
}

function escapeHtml(value) {
    return String(value)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

function escapeAttribute(value) {
    return escapeHtml(value);
}