let etlOverview = null;
let etlSelectedPeerId = null;
let etlManuscriptsTable = null;
let etlPeerManuscripts = [];
let etlPendingOperations = 0;
let etlActiveConflict = null;
let etlConflictWorkflow = null;

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

    const applyRemoteButton = document.getElementById('etl-conflict-apply-remote');
    if (applyRemoteButton) {
        applyRemoteButton.addEventListener('click', async () => {
            await resolveActiveConflict('apply_remote');
        });
    }

    const keepLocalButton = document.getElementById('etl-conflict-keep-local');
    if (keepLocalButton) {
        keepLocalButton.addEventListener('click', async () => {
            await resolveActiveConflict('keep_local');
        });
    }

    const closeConflictButton = document.getElementById('etl-conflict-close');
    if (closeConflictButton) {
        closeConflictButton.addEventListener('click', () => {
            appendETLLog('Closed conflict review panel and discarded the pending conflict workflow.');
            clearActiveConflict({ resetWorkflow: true });
        });
    }
}

async function loadETLOverview() {
    beginETLBusyState('Loading ETL overview...');
    try {
        const payload = await etlFetchJson('/api/etl/ui/overview/');
        etlOverview = payload;
        renderLocalSummary();
        renderPeerOptions();
        renderSelectedPeerStatus();
        appendETLLog('ETL overview loaded.');
    } catch (error) {
        appendETLLog(`Overview error: ${error.message}`);
    } finally {
        endETLBusyState();
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
    etlConflictWorkflow = {
        peerId: peer.id,
        peerUrl: peer.url,
        category,
        since: sinceValue,
        forceRemoteUuids: [],
        keepLocalUuids: [],
    };
    clearActiveConflict();
    appendETLLog(`Pulling ${category} from ${peer.url}${sinceValue ? ` since ${sinceValue}` : ''}...`);
    beginETLBusyState(`Pulling ${category} data...`);

    try {
        const payload = await etlFetchJson('/api/etl/ui/pull-category/', {
            method: 'POST',
            body: JSON.stringify({
                peer: peer.id,
                category: category,
                since: sinceValue,
                force_remote_uuids: etlConflictWorkflow.forceRemoteUuids,
                keep_local_uuids: etlConflictWorkflow.keepLocalUuids,
            }),
        });

        const result = payload.result || {};
        const importSummary = result.import_summary || {};
        const deleteSummary = result.delete_summary || {};
        clearActiveConflict({ resetWorkflow: true });
        appendETLLog(
            `${category} pull completed: created=${importSummary.created || 0}, updated=${importSummary.updated || 0}, skipped=${importSummary.skipped || 0}, deleted=${deleteSummary.deleted || 0}, missing_deleted=${deleteSummary.missing || 0}.`
        );
    } catch (error) {
        if (error.status === 409 && error.payload && error.payload.conflict) {
            updateConflictWorkflowFromPayload(error.payload);
            etlActiveConflict = error.payload.conflict;
            renderActiveConflict();
            appendETLLog(
                `${category} pull stopped on conflict for ${etlActiveConflict.model} uuid=${etlActiveConflict.object_uuid}. Choose keep-local or apply-remote to continue.`
            );
            return;
        }
        clearActiveConflict({ resetWorkflow: true });
        appendETLLog(`${category} pull failed: ${error.message}`);
    } finally {
        endETLBusyState();
    }
}

async function loadPeerManuscripts() {
    const peer = getSelectedPeer();
    if (!peer) {
        appendETLLog('Select a peer before loading manuscript packages.');
        return;
    }

    appendETLLog(`Loading manuscript packages from ${peer.url}...`);
    beginETLBusyState('Loading manuscript packages...');
    try {
        const payload = await etlFetchJson(`/api/etl/ui/manuscripts/?peer=${encodeURIComponent(peer.id)}`);
        etlPeerManuscripts = ((payload.payload || {}).results || []);
        renderPeerManuscriptsTable();
        appendETLLog(`Loaded ${etlPeerManuscripts.length} manuscript packages from ${peer.url}.`);
    } catch (error) {
        appendETLLog(`Cannot load manuscript packages: ${error.message}`);
    } finally {
        endETLBusyState();
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
    beginETLBusyState('Importing manuscript package...');
    try {
        const payload = await etlFetchJson('/api/etl/ui/pull-manuscript/', {
            method: 'POST',
            body: JSON.stringify({
                peer: peer.id,
                manuscript_uuid: manuscriptUuid,
            }),
        });
        const importSummary = (payload.result || {}).import_summary || {};
        const mediaSummary = importSummary.media_summary || {};
        appendETLLog(
            `Manuscript import completed: created=${importSummary.created || 0}, updated=${importSummary.updated || 0}, skipped=${importSummary.skipped || 0}, media_created=${mediaSummary.created || 0}, media_updated=${mediaSummary.updated || 0}, media_skipped=${mediaSummary.skipped || 0}.`
        );
    } catch (error) {
        appendETLLog(`Manuscript import failed: ${error.message}`);
    } finally {
        endETLBusyState();
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
        const error = new Error(payload.detail || `HTTP ${response.status}`);
        error.status = response.status;
        error.payload = payload;
        throw error;
    }

    return payload;
}

async function resolveActiveConflict(resolution) {
    if (!etlActiveConflict) {
        appendETLLog('No active conflict to resolve.');
        return;
    }
    if (!etlConflictWorkflow) {
        appendETLLog('No active conflict workflow to continue. Start the shared pull again.');
        return;
    }

    beginETLBusyState('Resolving shared conflict...');
    try {
        const payload = await etlFetchJson('/api/etl/ui/resolve-conflict/', {
            method: 'POST',
            body: JSON.stringify({
                resolution,
                conflict: etlActiveConflict,
                peer: etlConflictWorkflow.peerId,
                category: etlConflictWorkflow.category,
                since: etlConflictWorkflow.since,
                force_remote_uuids: etlConflictWorkflow.forceRemoteUuids,
                keep_local_uuids: etlConflictWorkflow.keepLocalUuids,
            }),
        });

        const result = payload.result || {};
        updateConflictWorkflowFromPayload(result);
        const pullResult = result.pull_result || {};
        const importSummary = pullResult.import_summary || {};
        const deleteSummary = pullResult.delete_summary || {};
        appendETLLog(
            `Conflict resolved: resolution=${result.resolution || resolution}, created=${importSummary.created || 0}, updated=${importSummary.updated || 0}, skipped=${importSummary.skipped || 0}, deleted=${deleteSummary.deleted || 0}.`
        );
        clearActiveConflict({ resetWorkflow: true });
    } catch (error) {
        if (error.status === 409 && error.payload && error.payload.conflict) {
            updateConflictWorkflowFromPayload(error.payload);
            etlActiveConflict = error.payload.conflict;
            renderActiveConflict();
            appendETLLog(
                `Another conflict requires review for ${etlActiveConflict.model} uuid=${etlActiveConflict.object_uuid}.`
            );
            return;
        }
        appendETLLog(`Conflict resolution failed: ${error.message}`);
    } finally {
        endETLBusyState();
    }
}

function updateConflictWorkflowFromPayload(payload) {
    if (!etlConflictWorkflow) {
        return;
    }

    etlConflictWorkflow.forceRemoteUuids = [...new Set(payload.force_remote_uuids || etlConflictWorkflow.forceRemoteUuids || [])];
    etlConflictWorkflow.keepLocalUuids = [...new Set(payload.keep_local_uuids || etlConflictWorkflow.keepLocalUuids || [])];
}

function clearActiveConflict(options = {}) {
    const { resetWorkflow = false } = options;
    etlActiveConflict = null;
    if (resetWorkflow) {
        etlConflictWorkflow = null;
    }
    renderActiveConflict();
}

function renderActiveConflict() {
    const panel = document.getElementById('etl-conflict-panel');
    const meta = document.getElementById('etl-conflict-meta');
    const progress = document.getElementById('etl-conflict-progress');
    const differencesBody = document.getElementById('etl-conflict-differences');
    const localRecord = document.getElementById('etl-conflict-local');
    const incomingRecord = document.getElementById('etl-conflict-incoming');

    if (!panel || !meta || !progress || !differencesBody || !localRecord || !incomingRecord) {
        return;
    }

    if (!etlActiveConflict) {
        panel.classList.add('hidden');
        meta.textContent = '';
        progress.textContent = '';
        differencesBody.innerHTML = '';
        localRecord.textContent = '';
        incomingRecord.textContent = '';
        return;
    }

    panel.classList.remove('hidden');
    meta.textContent = `${etlActiveConflict.model || 'Unknown model'} | uuid=${etlActiveConflict.object_uuid || 'n/a'} | reason=${etlActiveConflict.reason || 'unknown'} | local version=${etlActiveConflict.current_version ?? 'n/a'} | incoming version=${etlActiveConflict.incoming_version ?? 'n/a'}`;
    progress.textContent = `Queued decisions: keep-local=${(etlConflictWorkflow && etlConflictWorkflow.keepLocalUuids.length) || 0}, apply-remote=${(etlConflictWorkflow && etlConflictWorkflow.forceRemoteUuids.length) || 0}.`;

    const differences = etlActiveConflict.differences || [];
    differencesBody.innerHTML = differences.map((difference) => `
        <tr>
            <td class="border border-[#eadfd6] px-3 py-2 align-top font-semibold text-[#0d1b2a]">${escapeHtml(difference.field || '')}</td>
            <td class="border border-[#eadfd6] px-3 py-2 align-top text-[#203040]">${formatConflictValue(difference.local)}</td>
            <td class="border border-[#eadfd6] px-3 py-2 align-top text-[#203040]">${formatConflictValue(difference.incoming)}</td>
        </tr>
    `).join('') || '<tr><td colspan="3" class="border border-[#eadfd6] px-3 py-2 text-[#3d4b5c]">No field differences available.</td></tr>';

    localRecord.textContent = JSON.stringify(etlActiveConflict.local_record || {}, null, 2);
    incomingRecord.textContent = JSON.stringify(etlActiveConflict.incoming_record || {}, null, 2);
}

function formatConflictValue(value) {
    if (value === null || value === undefined) {
        return '<span class="text-[#8a6d55]">null</span>';
    }

    if (typeof value === 'object') {
        return `<pre class="whitespace-pre-wrap break-words text-xs">${escapeHtml(JSON.stringify(value, null, 2))}</pre>`;
    }

    return `<span class="break-words">${escapeHtml(String(value))}</span>`;
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
    const separator = container.textContent ? '\n' : '';
    container.textContent += `${separator}[${timestamp}] ${message}`;
    container.scrollTop = container.scrollHeight;
}

function beginETLBusyState(message) {
    etlPendingOperations += 1;
    renderETLBusyState(message || 'Working...');
}

function endETLBusyState() {
    etlPendingOperations = Math.max(0, etlPendingOperations - 1);
    renderETLBusyState();
}

function renderETLBusyState(message) {
    const panel = document.getElementById('etl-busy-panel');
    const text = document.getElementById('etl-busy-text');
    const controls = document.querySelectorAll('#etl-refresh-overview, #etl-load-manuscripts, .etl-sync-category, #etl-peer-select, #etl-since, .etl-import-manuscript');
    const isBusy = etlPendingOperations > 0;

    if (panel) {
        panel.classList.toggle('hidden', !isBusy);
        panel.setAttribute('aria-busy', isBusy ? 'true' : 'false');
    }

    if (text && message) {
        text.textContent = message;
    }

    controls.forEach((element) => {
        if ('disabled' in element) {
            element.disabled = isBusy;
        }
        element.classList.toggle('opacity-60', isBusy);
        element.classList.toggle('cursor-not-allowed', isBusy);
    });
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