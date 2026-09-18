/*
 * Prayer hover cards.
 *
 * A CO number in a table tells a reader nothing about which prayer it is, and an
 * incipit is cut short. This puts the full text — with its traditions, its
 * translation and how widely it is attested — one hover away, anywhere a prayer
 * is named.
 *
 * Nothing is loaded up front. The page renders its tables with plain markers and
 * only the prayer actually pointed at is fetched, so none of this competes with
 * the artifacts the page is still loading. Three things keep it cheap:
 *
 *   - one delegated listener on the document, so marking up ten thousand cells
 *     costs nothing and markup rendered later is picked up without re-binding;
 *   - requests are batched inside a short window, so sweeping the mouse across a
 *     table produces one request carrying every prayer it passed over, not fifty;
 *   - every answer is cached for the life of the page, and a key already in
 *     flight is never requested twice.
 *
 * Markup it reacts to:
 *   <span data-prayer-uuid="…">1623</span>   exact, always one prayer
 *   <span data-prayer-co="1623">1623</span>  fallback for artifacts written
 *                                            before uuids were carried through;
 *                                            CO numbers are not unique in this
 *                                            data, so the card shows every match.
 */
window.PrayerHover = (function () {
  'use strict';

  /** How long to wait for more keys before sending a batch. One mouse sweep. */
  const BATCH_WINDOW_MS = 35;
  /** Keys per request. The endpoint refuses more than 80 of either kind. */
  const MAX_BATCH = 60;
  /** Pointing at something for this long counts as wanting to read it. */
  const OPEN_DELAY_MS = 130;
  /** Grace period so the pointer can travel from the marker into the card. */
  const CLOSE_DELAY_MS = 220;

  const SELECTOR = '[data-prayer-uuid],[data-prayer-co]';

  let endpoint = null;
  let installed = false;

  /** key ("u:<uuid>" / "c:<co no>") -> {status, formulas} */
  const cache = new Map();
  /** Keys waiting to go out in the next batch. */
  let queued = [];
  let queueTimer = null;

  let card = null;
  let anchor = null;
  let openTimer = null;
  let closeTimer = null;
  let pointerInCard = false;
  // A card opened deliberately - clicked or tapped - stays until it is dismissed.
  // Without this a tap would open the card on focus and close it again on the
  // click that follows, which is every touch device.
  let pinned = false;

  /* ---------------------------------------------------------------- *
   * Fetching
   * ---------------------------------------------------------------- */

  function keyFor(element) {
    const uuid = element.getAttribute('data-prayer-uuid');
    if (uuid) return 'u:' + uuid;
    const co = element.getAttribute('data-prayer-co');
    return co ? 'c:' + co : null;
  }

  function request(key) {
    if (cache.has(key)) return;
    cache.set(key, { status: 'loading', formulas: [] });
    queued.push(key);
    if (queued.length >= MAX_BATCH) return flushQueue();
    if (queueTimer === null) queueTimer = setTimeout(flushQueue, BATCH_WINDOW_MS);
  }

  function flushQueue() {
    if (queueTimer !== null) {
      clearTimeout(queueTimer);
      queueTimer = null;
    }
    const batch = queued.splice(0, MAX_BATCH);
    if (!batch.length) return;
    if (queued.length) queueTimer = setTimeout(flushQueue, 0);

    const uuids = [];
    const coNos = [];
    batch.forEach(function (key) {
      (key.charAt(0) === 'u' ? uuids : coNos).push(key.slice(2));
    });

    const params = [];
    if (uuids.length) params.push('uuid=' + uuids.map(encodeURIComponent).join(','));
    if (coNos.length) params.push('co=' + coNos.map(encodeURIComponent).join(','));

    fetch(endpoint + '?' + params.join('&'), { credentials: 'include' })
      .then(function (response) {
        if (!response.ok) throw new Error('lookup failed');
        return response.json();
      })
      .then(function (payload) {
        // Answers come back unordered and a CO number may match several
        // formulas, so they are bucketed by both keys and then every requested
        // key is resolved - including the ones nothing matched.
        const byUuid = new Map();
        const byCo = new Map();
        (payload.formulas || []).forEach(function (formula) {
          if (formula.uuid) byUuid.set('u:' + formula.uuid, [formula]);
          if (formula.co_no) {
            const key = 'c:' + formula.co_no;
            if (!byCo.has(key)) byCo.set(key, []);
            byCo.get(key).push(formula);
          }
        });
        batch.forEach(function (key) {
          const found = (key.charAt(0) === 'u' ? byUuid : byCo).get(key) || [];
          cache.set(key, { status: found.length ? 'ok' : 'missing', formulas: found });
        });
      })
      .catch(function () {
        batch.forEach(function (key) {
          // Dropped rather than remembered as failed: the next hover retries.
          cache.delete(key);
        });
      })
      .then(function () {
        // The tab may have been redrawn, and with it the marker this card belongs to.
        if (anchor && !anchor.isConnected) return close();
        if (anchor && card && card.style.display === 'block') renderCard(anchor);
      });
  }

  /* ---------------------------------------------------------------- *
   * The card
   * ---------------------------------------------------------------- */

  function escapeHtml(value) {
    if (value === null || value === undefined) return '';
    return String(value)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function ensureStyles() {
    if (document.getElementById('prayerHoverStyles')) return;
    const style = document.createElement('style');
    style.id = 'prayerHoverStyles';
    style.textContent = [
      '.prayer-ref{cursor:help;}',
      // An opaque marker - a bare CO number - advertises itself. A long stretch
      // of text does not need to: a whole column of dotted underlines is noise,
      // so those reveal themselves under the pointer instead.
      '.prayer-ref:not(.prayer-ref--quiet),.prayer-ref:hover,.prayer-ref:focus{',
      '  text-decoration:underline dotted #b08968;',
      '  text-underline-offset:2px;text-decoration-thickness:1px;}',
      '.prayer-ref:hover,.prayer-ref:focus{background:#f7ede3;outline:none;}',
      '#prayerHoverCard{position:fixed;z-index:10000;display:none;',
      '  max-width:min(460px,92vw);max-height:60vh;overflow:auto;',
      '  background:#fffdfb;color:#0d1b2a;border:1px solid #e3d5ca;border-radius:6px;',
      '  box-shadow:0 6px 24px rgba(13,27,42,0.18);padding:10px 12px;',
      '  font-size:13px;line-height:1.5;}',
      '#prayerHoverCard .ph-co{font-weight:700;font-size:14px;}',
      '#prayerHoverCard .ph-text{margin-top:4px;white-space:pre-wrap;}',
      '#prayerHoverCard .ph-translation{margin-top:6px;color:#4a5568;font-style:italic;',
      '  white-space:pre-wrap;}',
      '#prayerHoverCard .ph-meta{margin-top:6px;font-size:11px;color:#6b7280;}',
      '#prayerHoverCard .ph-tradition{display:inline-block;margin:2px 4px 0 0;padding:1px 6px;',
      '  border-radius:9999px;background:#efe6de;font-size:11px;}',
      '#prayerHoverCard .ph-entry + .ph-entry{margin-top:10px;padding-top:10px;',
      '  border-top:1px solid #efe6de;}',
      // A hover card is a reading aid, never part of the printed document.
      '@media print{#prayerHoverCard{display:none !important;}',
      '.prayer-ref{text-decoration:none;background:none;}}',
    ].join('\n');
    document.head.appendChild(style);
  }

  function ensureCard() {
    if (card) return card;
    ensureStyles();
    card = document.createElement('div');
    card.id = 'prayerHoverCard';
    card.setAttribute('role', 'tooltip');
    // Readable rather than glanceable: the pointer may enter it to scroll a long
    // prayer or to select the text.
    card.addEventListener('mouseenter', function () {
      pointerInCard = true;
      clearTimeout(closeTimer);
    });
    card.addEventListener('mouseleave', function () {
      pointerInCard = false;
      scheduleClose();
    });
    document.body.appendChild(card);
    return card;
  }

  function truncate(text, limit) {
    if (!text || text.length <= limit) return text || '';
    return text.slice(0, limit).replace(/\s+\S*$/, '') + '…';
  }

  function entryHtml(formula) {
    const traditions = (formula.traditions || []).map(function (tradition) {
      const colour = /^#?[0-9a-fA-F]{6}$/.test(tradition.color_rgb || '')
        ? (tradition.color_rgb.charAt(0) === '#' ? tradition.color_rgb : '#' + tradition.color_rgb)
        : null;
      return '<span class="ph-tradition"' +
        (colour ? ' style="background:' + colour + '33"' : '') + '>' +
        escapeHtml(tradition.name) + '</span>';
    }).join('');

    const meta = [];
    if (formula.manuscripts) {
      meta.push(formula.manuscripts + ' manuscript' + (formula.manuscripts === 1 ? '' : 's'));
    }
    if (formula.occurrences) {
      meta.push(formula.occurrences + ' occurrence' + (formula.occurrences === 1 ? '' : 's'));
    }

    return '<div class="ph-entry">' +
      '<div class="ph-co">' + escapeHtml(formula.co_no || 'No CO number') + '</div>' +
      (traditions ? '<div>' + traditions + '</div>' : '') +
      '<div class="ph-text">' +
      escapeHtml(truncate(formula.text, 1400) || 'No text recorded.') + '</div>' +
      (formula.translation_en
        ? '<div class="ph-translation">' +
          escapeHtml(truncate(formula.translation_en, 900)) + '</div>'
        : '') +
      (meta.length ? '<div class="ph-meta">' + escapeHtml(meta.join(' · ')) + '</div>' : '') +
      '</div>';
  }

  function renderCard(element) {
    const key = keyFor(element);
    const entry = key ? cache.get(key) : null;
    const node = ensureCard();

    if (!entry || entry.status === 'loading') {
      node.innerHTML = '<div class="ph-meta">Loading the prayer…</div>';
    } else if (entry.status === 'missing' || !entry.formulas.length) {
      node.innerHTML = '<div class="ph-meta">This prayer is no longer in the database.</div>';
    } else {
      // A CO number matching several formulas is a fact about the data, not an
      // error, so all of them are shown rather than one picked arbitrarily.
      const ambiguous = entry.formulas.length > 1
        ? '<div class="ph-meta">CO ' + escapeHtml(element.getAttribute('data-prayer-co')) +
          ' is recorded against ' + entry.formulas.length + ' different texts.</div>'
        : '';
      node.innerHTML = ambiguous + entry.formulas.map(entryHtml).join('');
    }

    position(element, node);
  }

  function position(element, node) {
    node.style.display = 'block';
    // Measured after the content is in, so a short card is not placed as if it
    // were tall and flipped for no reason.
    node.style.left = '0px';
    node.style.top = '0px';
    const box = element.getBoundingClientRect();
    const size = node.getBoundingClientRect();
    const gap = 8;

    let left = box.left;
    if (left + size.width > window.innerWidth - gap) {
      left = Math.max(gap, window.innerWidth - size.width - gap);
    }

    let top = box.bottom + gap;
    if (top + size.height > window.innerHeight - gap) {
      const above = box.top - size.height - gap;
      top = above >= gap ? above : Math.max(gap, window.innerHeight - size.height - gap);
    }

    node.style.left = Math.round(left) + 'px';
    node.style.top = Math.round(top) + 'px';
  }

  function open(element, pin) {
    // The tab may have been redrawn while the open delay was running.
    if (!element.isConnected) return;
    // Moving to a different prayer starts again: a card pinned to the previous
    // one must not make the click that opens this one read as a dismissal.
    if (element !== anchor) pinned = false;
    anchor = element;
    if (pin) pinned = true;
    const key = keyFor(element);
    if (key) request(key);
    renderCard(element);
  }

  function close() {
    anchor = null;
    pinned = false;
    pointerInCard = false;
    if (card) card.style.display = 'none';
  }

  function scheduleClose() {
    if (pinned) return;
    clearTimeout(closeTimer);
    closeTimer = setTimeout(function () {
      if (!pointerInCard && !pinned) close();
    }, CLOSE_DELAY_MS);
  }

  /* ---------------------------------------------------------------- *
   * Wiring
   * ---------------------------------------------------------------- */

  function markerFrom(event) {
    const target = event.target;
    if (!target || !target.closest) return null;
    return target.closest(SELECTOR);
  }

  function install() {
    if (installed) return;
    installed = true;
    // Up front, not on first hover: the markers have to look hoverable before
    // anyone hovers one.
    ensureStyles();

    document.addEventListener('mouseover', function (event) {
      const element = markerFrom(event);
      if (!element) return;
      clearTimeout(closeTimer);
      clearTimeout(openTimer);
      // The fetch starts at once while the card waits: by the time a deliberate
      // hover has been established the text is usually already here.
      const key = keyFor(element);
      if (key) request(key);
      openTimer = setTimeout(function () { open(element); }, OPEN_DELAY_MS);
    }, true);

    document.addEventListener('mouseout', function (event) {
      if (!markerFrom(event)) return;
      clearTimeout(openTimer);
      scheduleClose();
    }, true);

    // Keyboard and touch both need the card without a pointer hovering.
    document.addEventListener('focusin', function (event) {
      const element = markerFrom(event);
      if (element) open(element);
    });
    document.addEventListener('focusout', function (event) {
      if (markerFrom(event)) scheduleClose();
    });
    document.addEventListener('click', function (event) {
      const element = markerFrom(event);
      if (!element) {
        // Reading inside the card - scrolling it, selecting the text - is not a
        // request to dismiss it.
        if (card && card.contains(event.target)) return;
        return close();
      }
      clearTimeout(openTimer);
      if (anchor === element && pinned) return close();
      open(element, true);
    });
    document.addEventListener('keydown', function (event) {
      if (event.key === 'Escape') close();
    });
    // A card placed in viewport coordinates would otherwise drift away from the
    // marker it belongs to. Scrolling a long prayer inside the card is not that.
    window.addEventListener('scroll', function (event) {
      if (!anchor) return;
      if (card && event.target && event.target.nodeType === 1
        && card.contains(event.target)) return;
      close();
    }, true);
    window.addEventListener('resize', function () { if (anchor) close(); });
  }

  /**
   * @param {{endpoint: string}} options where to resolve prayer references.
   */
  function init(options) {
    endpoint = (options && options.endpoint) || endpoint;
    if (!endpoint) return;
    install();
  }

  /**
   * Markup for one prayer reference, for renderers building HTML strings.
   *
   * `reference` is either a uuid, or a CO number when that is all an artifact
   * carries. Text with no reference is returned escaped and inert, so a caller
   * never has to branch.
   *
   * @param {{co?: boolean, quiet?: boolean}} [options] `co` when the reference is
   *   a CO number rather than a uuid; `quiet` for markers that should not carry a
   *   standing underline, such as a whole incipit.
   */
  function markup(text, reference, options) {
    const label = escapeHtml(text === null || text === undefined ? '' : text);
    if (!reference) return label;
    const settings = options || {};
    const attribute = settings.co ? 'data-prayer-co' : 'data-prayer-uuid';
    return '<span class="prayer-ref' + (settings.quiet ? ' prayer-ref--quiet' : '') +
      '" tabindex="0" ' + attribute + '="' + escapeHtml(reference) + '">' +
      label + '</span>';
  }

  return {
    init: init,
    markup: markup,
    close: close,
    /** Warm the cache for formulas the caller knows will be wanted. */
    prefetch: function (uuids) {
      (uuids || []).forEach(function (uuid) { request('u:' + uuid); });
    },
  };
})();
