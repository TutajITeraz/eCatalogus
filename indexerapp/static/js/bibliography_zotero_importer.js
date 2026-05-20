(function () {
    function getCookie(name) {
        const cookies = document.cookie ? document.cookie.split(';') : [];
        for (const rawCookie of cookies) {
            const cookie = rawCookie.trim();
            if (cookie.startsWith(`${name}=`)) {
                return decodeURIComponent(cookie.slice(name.length + 1));
            }
        }
        return '';
    }

    function escapeHtml(value) {
        return String(value)
            .replaceAll('&', '&amp;')
            .replaceAll('<', '&lt;')
            .replaceAll('>', '&gt;')
            .replaceAll('"', '&quot;')
            .replaceAll("'", '&#39;');
    }

    function iconSvg(paths) {
        return `<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">${paths}</svg>`;
    }

    document.addEventListener('DOMContentLoaded', function () {
        const shell = document.getElementById('zotero-importer-shell');
        if (!shell) {
            return;
        }

        const treeUrl = shell.dataset.treeUrl;
        const importUrl = shell.dataset.importUrl;
        const collectionItemsUrl = shell.dataset.collectionItemsUrl;
        const csrfToken = shell.dataset.csrfToken;
        const configReady = shell.dataset.configReady === 'true';
        const treeRoot = document.getElementById('zotero-tree-root');
        const treeStatus = document.getElementById('zotero-tree-status');
        const manuscriptSelect = document.getElementById('zotero-manuscript-select');
        const manuscriptAutocompleteUrl = manuscriptSelect ? manuscriptSelect.dataset.autocompleteUrl : '';
        const selectedItemsList = document.getElementById('zotero-selected-items');
        const feedback = document.getElementById('zotero-feedback');
        const importButton = document.getElementById('zotero-import-selected');
        const reloadButton = document.getElementById('zotero-reload-tree');
        const clearButton = document.getElementById('zotero-clear-selection');
        const selectedItems = new Map();
        const collectionElements = new Map();
        const loadedChildren = new Map();
        const subtreeItemsCache = new Map();
        const itemTypeIcons = {
            artwork: {
                css: 'item-artwork',
                svg: iconSvg('<path d="M5.75 19.25h12.5"></path><path d="M7.5 16.5 10 13l2.5 2.5 2-2 2.5 3"></path><circle cx="9" cy="9" r="1.25"></circle><rect x="4.75" y="4.75" width="14.5" height="12.5" rx="2"></rect>'),
            },
            audiorecording: {
                css: 'item-broadcast',
                svg: iconSvg('<path d="M12 5.25a2.25 2.25 0 0 1 2.25 2.25v4.5A2.25 2.25 0 0 1 12 14.25a2.25 2.25 0 0 1-2.25-2.25V7.5A2.25 2.25 0 0 1 12 5.25Z"></path><path d="M7.75 11.5a4.25 4.25 0 0 0 8.5 0"></path><path d="M12 15.75v3.5"></path><path d="M9.5 19.25h5"></path>'),
            },
            bill: {
                css: 'item-legal',
                svg: iconSvg('<path d="M8 7.25h8"></path><path d="M8 11.25h8"></path><path d="M8 15.25h5"></path><path d="M6.75 4.75h10.5A1.75 1.75 0 0 1 19 6.5v11a1.75 1.75 0 0 1-1.75 1.75H6.75A1.75 1.75 0 0 1 5 17.5v-11a1.75 1.75 0 0 1 1.75-1.75Z"></path>'),
            },
            blogpost: {
                css: 'item-webpage',
                svg: iconSvg('<path d="M7.5 8.5h9"></path><path d="M7.5 12h7"></path><path d="M7.5 15.5h5"></path><path d="M6.75 4.75h10.5A1.75 1.75 0 0 1 19 6.5v11a1.75 1.75 0 0 1-1.75 1.75H6.75A1.75 1.75 0 0 1 5 17.5v-11a1.75 1.75 0 0 1 1.75-1.75Z"></path>'),
            },
            book: {
                css: 'item-book',
                svg: iconSvg('<path d="M6.5 5.25h9.25A2.25 2.25 0 0 1 18 7.5v10.75H8.75A2.75 2.75 0 0 0 6 21V7.75a2.5 2.5 0 0 1 2.5-2.5Z"></path><path d="M18 18.25H8.75A2.75 2.75 0 0 0 6 21"></path><path d="M9 8.75h6"></path>'),
            },
            booksection: {
                css: 'item-booksection',
                svg: iconSvg('<path d="M6.5 5.25h9.25A2.25 2.25 0 0 1 18 7.5v10.75H8.75A2.75 2.75 0 0 0 6 21V7.75a2.5 2.5 0 0 1 2.5-2.5Z"></path><path d="M9 8.5h5.5"></path><path d="M9 11.5h5.5"></path><path d="M9 14.5h3.5"></path>'),
            },
            case: {
                css: 'item-legal',
                svg: iconSvg('<path d="M8 7.25h8"></path><path d="M12 7.25v10"></path><path d="M9.5 17.25h5"></path><path d="M7 9.25 5.5 12h3L7 9.25Z"></path><path d="M17 9.25 15.5 12h3L17 9.25Z"></path>'),
            },
            computerprogram: {
                css: 'item-code',
                svg: iconSvg('<path d="m9.25 9.25-3 2.75 3 2.75"></path><path d="m14.75 9.25 3 2.75-3 2.75"></path><path d="m13.25 7.5-2.5 9"></path>'),
            },
            conferencepaper: {
                css: 'item-presentation',
                svg: iconSvg('<path d="M6 6.25h12"></path><path d="M8 6.25v7.5"></path><path d="M16 6.25v7.5"></path><path d="M10 17.75h4"></path><path d="M12 13.75v4"></path>'),
            },
            dataset: {
                css: 'item-presentation',
                svg: iconSvg('<ellipse cx="12" cy="7" rx="5.5" ry="2.25"></ellipse><path d="M6.5 7v5c0 1.25 2.46 2.25 5.5 2.25s5.5-1 5.5-2.25V7"></path><path d="M6.5 12v5c0 1.25 2.46 2.25 5.5 2.25s5.5-1 5.5-2.25v-5"></path>'),
            },
            dictionaryentry: {
                css: 'item-reference',
                svg: iconSvg('<path d="M7 5.75h10"></path><path d="M7 9.75h6"></path><path d="M7 13.75h10"></path><path d="M7 17.75h6"></path><path d="M5.75 4.75h1.5v14.5h-1.5z"></path>'),
            },
            document: {
                css: 'item-document',
                svg: iconSvg('<path d="M8 4.75h5.75L18 9v10.25H8A1.75 1.75 0 0 1 6.25 17.5v-11A1.75 1.75 0 0 1 8 4.75Z"></path><path d="M13.75 4.75V9H18"></path><path d="M9.25 12h5.5"></path><path d="M9.25 15.25h5.5"></path>'),
            },
            email: {
                css: 'item-communication',
                svg: iconSvg('<rect x="4.75" y="6.5" width="14.5" height="11" rx="2"></rect><path d="m6.5 8 5.5 4 5.5-4"></path>'),
            },
            encyclopediaarticle: {
                css: 'item-reference',
                svg: iconSvg('<path d="M7 5.75h10"></path><path d="M7 9.75h6"></path><path d="M7 13.75h10"></path><path d="M7 17.75h6"></path><path d="M5.75 4.75h1.5v14.5h-1.5z"></path>'),
            },
            film: {
                css: 'item-media',
                svg: iconSvg('<rect x="5.25" y="6.25" width="13.5" height="11.5" rx="2"></rect><path d="M8 6.25v11.5"></path><path d="M16 6.25v11.5"></path><path d="M5.25 10h13.5"></path><path d="M5.25 14h13.5"></path>'),
            },
            forumpost: {
                css: 'item-webpage',
                svg: iconSvg('<path d="M7.5 8h9"></path><path d="M7.5 12h6"></path><path d="M8 18.5 5.5 20v-3.25A2.25 2.25 0 0 1 3.25 14.5v-7A2.25 2.25 0 0 1 5.5 5.25h13A2.25 2.25 0 0 1 20.75 7.5v7a2.25 2.25 0 0 1-2.25 2.25H8Z"></path>'),
            },
            hearing: {
                css: 'item-legal',
                svg: iconSvg('<path d="M5.5 18.25h13"></path><path d="M8 18.25V9.5"></path><path d="M12 18.25V9.5"></path><path d="M16 18.25V9.5"></path><path d="m4.75 9.5 7.25-4.75 7.25 4.75H4.75Z"></path>'),
            },
            instantmessage: {
                css: 'item-communication',
                svg: iconSvg('<path d="M7.5 8h9"></path><path d="M7.5 12h6"></path><path d="M8 18.5 5.5 20v-3.25A2.25 2.25 0 0 1 3.25 14.5v-7A2.25 2.25 0 0 1 5.5 5.25h13A2.25 2.25 0 0 1 20.75 7.5v7a2.25 2.25 0 0 1-2.25 2.25H8Z"></path>'),
            },
            interview: {
                css: 'item-communication',
                svg: iconSvg('<path d="M8.5 10.25a2.25 2.25 0 1 1 0-4.5 2.25 2.25 0 0 1 0 4.5Z"></path><path d="M15.5 12.75a2.25 2.25 0 1 1 0-4.5 2.25 2.25 0 0 1 0 4.5Z"></path><path d="M5.5 18.25a3 3 0 0 1 6 0"></path><path d="M12.5 18.25a3 3 0 0 1 6 0"></path>'),
            },
            journalarticle: {
                css: 'item-journalarticle',
                svg: iconSvg('<path d="M7.5 7.5h9"></path><path d="M7.5 11h9"></path><path d="M7.5 14.5h5"></path><rect x="4.75" y="4.75" width="14.5" height="14.5" rx="2"></rect>'),
            },
            letter: {
                css: 'item-communication',
                svg: iconSvg('<rect x="4.75" y="6.5" width="14.5" height="11" rx="2"></rect><path d="m6.5 8 5.5 4 5.5-4"></path>'),
            },
            magazinearticle: {
                css: 'item-magazinearticle',
                svg: iconSvg('<path d="M7.5 7.5h9"></path><path d="M7.5 11h9"></path><path d="M7.5 14.5h5"></path><rect x="4.75" y="4.75" width="14.5" height="14.5" rx="2"></rect>'),
            },
            manuscript: {
                css: 'item-manuscript',
                svg: iconSvg('<path d="M8 4.75h5.75L18 9v10.25H8A1.75 1.75 0 0 1 6.25 17.5v-11A1.75 1.75 0 0 1 8 4.75Z"></path><path d="M13.75 4.75V9H18"></path><path d="M9 12.5c1-.8 2-.8 3 0s2 .8 3 0"></path><path d="M9 15.5c1-.8 2-.8 3 0s2 .8 3 0"></path>'),
            },
            map: {
                css: 'item-artwork',
                svg: iconSvg('<path d="m4.75 6.5 4-1.75 6.5 2.5 4-1.75v12l-4 1.75-6.5-2.5-4 1.75v-12Z"></path><path d="M8.75 4.75v12"></path><path d="M15.25 7.25v12"></path>'),
            },
            newspaperarticle: {
                css: 'item-newspaperarticle',
                svg: iconSvg('<rect x="4.75" y="5.25" width="14.5" height="13.5" rx="2"></rect><path d="M8 8.5h8"></path><path d="M8 11.5h8"></path><path d="M8 14.5h5"></path><path d="M6.75 8.25h.01"></path>'),
            },
            note: {
                css: 'item-document',
                svg: iconSvg('<path d="M8 4.75h5.75L18 9v10.25H8A1.75 1.75 0 0 1 6.25 17.5v-11A1.75 1.75 0 0 1 8 4.75Z"></path><path d="M13.75 4.75V9H18"></path><path d="M9.25 12h5.5"></path><path d="M9.25 15.25h4"></path>'),
            },
            patent: {
                css: 'item-legal',
                svg: iconSvg('<path d="m9.25 13.5 5.5-5.5"></path><path d="m13.25 7.5 3.25 3.25"></path><path d="M8.25 18.25a3 3 0 1 1-4.24-4.24l2.25-2.26 4.24 4.25-2.25 2.25Z"></path>'),
            },
            podcast: {
                css: 'item-broadcast',
                svg: iconSvg('<path d="M12 5.75a6.25 6.25 0 0 1 6.25 6.25"></path><path d="M12 8.75a3.25 3.25 0 0 1 3.25 3.25"></path><path d="M12 13.25a1.5 1.5 0 1 0 0-3 1.5 1.5 0 0 0 0 3Z"></path><path d="M12 14.75v3.5"></path><path d="M10.5 19.25h3"></path><path d="M5.75 12A6.25 6.25 0 0 1 12 5.75"></path>'),
            },
            preprint: {
                css: 'item-preprint',
                svg: iconSvg('<path d="M8 4.75h5.75L18 9v10.25H8A1.75 1.75 0 0 1 6.25 17.5v-11A1.75 1.75 0 0 1 8 4.75Z"></path><path d="M13.75 4.75V9H18"></path><path d="m10 14 2 2 3-4"></path>'),
            },
            presentation: {
                css: 'item-presentation',
                svg: iconSvg('<path d="M6 6.25h12"></path><path d="M8 6.25v7.5"></path><path d="M16 6.25v7.5"></path><path d="M10 17.75h4"></path><path d="M12 13.75v4"></path>'),
            },
            radiobroadcast: {
                css: 'item-broadcast',
                svg: iconSvg('<circle cx="12" cy="12" r="2.25"></circle><path d="M5.75 12a6.25 6.25 0 0 1 12.5 0"></path><path d="M8.25 12a3.75 3.75 0 0 1 7.5 0"></path><path d="M8 18.25h8"></path>'),
            },
            report: {
                css: 'item-report',
                svg: iconSvg('<path d="M8 4.75h5.75L18 9v10.25H8A1.75 1.75 0 0 1 6.25 17.5v-11A1.75 1.75 0 0 1 8 4.75Z"></path><path d="M13.75 4.75V9H18"></path><path d="M9.25 15.25 11 13.5l1.5 1.5 2.25-3"></path>'),
            },
            standard: {
                css: 'item-legal',
                svg: iconSvg('<path d="M8 7.25h8"></path><path d="M8 11.25h8"></path><path d="M8 15.25h5"></path><path d="M6.75 4.75h10.5A1.75 1.75 0 0 1 19 6.5v11a1.75 1.75 0 0 1-1.75 1.75H6.75A1.75 1.75 0 0 1 5 17.5v-11a1.75 1.75 0 0 1 1.75-1.75Z"></path>'),
            },
            statute: {
                css: 'item-legal',
                svg: iconSvg('<path d="M8 7.25h8"></path><path d="M12 7.25v10"></path><path d="M9.5 17.25h5"></path><path d="M7 9.25 5.5 12h3L7 9.25Z"></path><path d="M17 9.25 15.5 12h3L17 9.25Z"></path>'),
            },
            thesis: {
                css: 'item-thesis',
                svg: iconSvg('<path d="M12 5.25 5.75 8.5 12 11.75 18.25 8.5 12 5.25Z"></path><path d="M8.5 10.5v3.25c0 1 1.6 1.75 3.5 1.75s3.5-.75 3.5-1.75V10.5"></path><path d="M18.25 8.5v4.25"></path>'),
            },
            tvbroadcast: {
                css: 'item-broadcast',
                svg: iconSvg('<rect x="5.25" y="7" width="13.5" height="9.5" rx="2"></rect><path d="M9.5 19.25h5"></path><path d="M12 16.5v2.75"></path><path d="m9.25 4.75 2.75 2.25 2.75-2.25"></path>'),
            },
            videorecording: {
                css: 'item-media',
                svg: iconSvg('<rect x="4.75" y="6.25" width="11.5" height="11.5" rx="2"></rect><path d="m16.25 10 3-1.75v7.5l-3-1.75"></path><path d="m10 10.25 3 1.75-3 1.75v-3.5"></path>'),
            },
            webpage: {
                css: 'item-webpage',
                svg: iconSvg('<circle cx="12" cy="12" r="7.25"></circle><path d="M4.75 12h14.5"></path><path d="M12 4.75a11.5 11.5 0 0 1 0 14.5"></path><path d="M12 4.75a11.5 11.5 0 0 0 0 14.5"></path>'),
            },
        };

        const fallbackItemIcon = {
            css: 'item-document',
            svg: iconSvg('<path d="M8 4.75h5.75L18 9v10.25H8A1.75 1.75 0 0 1 6.25 17.5v-11A1.75 1.75 0 0 1 8 4.75Z"></path><path d="M13.75 4.75V9H18"></path>'),
        };

        function showFeedback(kind, message) {
            feedback.className = `zotero-feedback ${kind}`;
            feedback.style.display = 'block';
            feedback.textContent = message;
        }

        function updateSelectedItemsView() {
            const items = Array.from(selectedItems.values());
            if (!items.length) {
                selectedItemsList.innerHTML = '<li>No items selected yet.</li>';
                return;
            }

            selectedItemsList.innerHTML = items.map((item) => `
                <li>
                    <strong>${escapeHtml(item.label)}</strong>
                    <div class="zotero-tree-meta">${escapeHtml(item.author || 'No author')} ${item.year ? `| ${escapeHtml(item.year)}` : ''} ${item.hierarchy ? `| level ${escapeHtml(item.hierarchy)}` : ''}</div>
                </li>
            `).join('');
        }

        function initializeManuscriptSelect() {
            if (!manuscriptSelect || !window.jQuery || !window.jQuery.fn || !window.jQuery.fn.select2) {
                return;
            }

            window.jQuery(manuscriptSelect).select2({
                ajax: {
                    url: manuscriptAutocompleteUrl,
                    dataType: 'json',
                    xhrFields: {
                        withCredentials: true,
                    },
                },
                placeholder: 'Select manuscript',
                allowClear: true,
                width: '100%',
            });
        }

        function setTreeStatus(message, loading) {
            if (!message) {
                treeStatus.innerHTML = '';
                return;
            }

            treeStatus.innerHTML = loading
                ? `<span class="zotero-main-spinner">${escapeHtml(message)}</span>`
                : escapeHtml(message);
        }

        function getItemTypeIcon(itemType) {
            const normalizedType = String(itemType || '').replace(/[^a-zA-Z0-9]/g, '').toLowerCase();
            if (itemTypeIcons[normalizedType]) {
                return itemTypeIcons[normalizedType];
            }

            return fallbackItemIcon;
        }

        function getCsrfToken() {
            if (csrfToken && csrfToken !== 'NOTPROVIDED') {
                return csrfToken;
            }
            const hiddenInput = document.querySelector('[name="csrfmiddlewaretoken"]');
            if (hiddenInput && hiddenInput.value) {
                return hiddenInput.value;
            }
            return getCookie('csrftoken');
        }

        function renderNodeList(nodes) {
            const fragment = document.createDocumentFragment();
            nodes.forEach((node) => {
                fragment.appendChild(node.node_type === 'collection' ? buildCollectionNode(node) : buildItemNode(node));
            });
            return fragment;
        }

        function syncRenderedSubtreeSelection(collectionKey, checked) {
            const collectionElement = collectionElements.get(collectionKey);
            if (!collectionElement) {
                return;
            }

            collectionElement.checkbox.checked = checked;
            collectionElement.checkbox.indeterminate = false;

            collectionElement.children.querySelectorAll('.zotero-node-checkbox').forEach((checkbox) => {
                checkbox.checked = checked;
                checkbox.indeterminate = false;
            });
        }

        function getLoadedCollectionItems(collectionKey) {
            const nodes = loadedChildren.get(collectionKey);
            if (!nodes) {
                return null;
            }

            let subtreeItems = [];
            for (const childNode of nodes) {
                if (childNode.node_type === 'item') {
                    subtreeItems.push(childNode);
                    continue;
                }

                const nestedItems = getLoadedCollectionItems(childNode.key);
                if (nestedItems === null) {
                    return null;
                }
                subtreeItems = subtreeItems.concat(nestedItems);
            }

            return subtreeItems;
        }

        async function fetchCollectionItems(collectionKey, hierarchy) {
            const url = new URL(collectionItemsUrl, window.location.origin);
            url.searchParams.set('collection_key', collectionKey);
            url.searchParams.set('hierarchy', hierarchy || 0);

            const response = await fetch(url, {
                headers: {
                    'X-Requested-With': 'XMLHttpRequest',
                },
                credentials: 'same-origin',
            });
            const payload = await response.json();
            if (!response.ok) {
                throw new Error(payload.error || 'Failed to load collection items.');
            }
            return payload.items || [];
        }

        async function toggleCollectionSelection(node, checkbox) {
            const shouldSelect = checkbox.checked;
            checkbox.disabled = true;
            showFeedback('info', `${shouldSelect ? 'Selecting' : 'Clearing'} all items from "${node.label}"...`);

            try {
                let subtreeItems = subtreeItemsCache.get(node.key);
                if (!subtreeItems) {
                    subtreeItems = getLoadedCollectionItems(node.key);
                }
                if (!subtreeItems) {
                    subtreeItems = await fetchCollectionItems(node.key, node.hierarchy);
                }
                subtreeItemsCache.set(node.key, subtreeItems);

                if (shouldSelect) {
                    subtreeItems.forEach((itemNode) => {
                        selectedItems.set(itemNode.key, itemNode);
                    });
                } else {
                    subtreeItems.forEach((itemNode) => {
                        selectedItems.delete(itemNode.key);
                    });
                }

                syncRenderedSubtreeSelection(node.key, shouldSelect);
                updateSelectedItemsView();
                showFeedback(
                    'success',
                    `${shouldSelect ? 'Selected' : 'Cleared'} ${subtreeItems.length} item(s) in "${node.label}" and its subcollections.`
                );
            } catch (error) {
                checkbox.checked = !shouldSelect;
                checkbox.indeterminate = false;
                showFeedback('error', error.message || 'Failed to update collection selection.');
            } finally {
                checkbox.disabled = false;
            }
        }

        function toggleItemSelection(node, checked) {
            if (checked) {
                selectedItems.set(node.key, node);
            } else {
                selectedItems.delete(node.key);
            }
            updateSelectedItemsView();
        }

        function buildItemNode(node) {
            const icon = getItemTypeIcon(node.item_type);
            const wrapper = document.createElement('li');
            wrapper.innerHTML = `
                <div class="zotero-tree-row">
                    <span class="zotero-item-icon ${escapeHtml(icon.css)}" aria-hidden="true" title="${escapeHtml(node.item_type || 'item')}">${icon.svg}</span>
                    <label class="zotero-item-label">
                        <input class="zotero-node-checkbox" data-node-type="item" type="checkbox" ${selectedItems.has(node.key) ? 'checked' : ''}>
                        <span class="zotero-item-details">
                            <strong>${escapeHtml(node.label)}</strong>
                            <div class="zotero-tree-meta">${escapeHtml(node.author || 'No author')}</div>
                            <div class="zotero-tree-meta">${node.year ? escapeHtml(node.year) : 'No year'}${node.item_type ? ` | ${escapeHtml(node.item_type)}` : ''}</div>
                        </span>
                    </label>
                </div>
            `;
            const checkbox = wrapper.querySelector('input[type="checkbox"]');
            checkbox.addEventListener('change', function () {
                toggleItemSelection(node, checkbox.checked);
            });
            return wrapper;
        }

        async function loadChildren(parentKey, hierarchy) {
            const url = new URL(treeUrl, window.location.origin);
            if (parentKey) {
                url.searchParams.set('parent', parentKey);
            }
            url.searchParams.set('hierarchy', hierarchy || 0);
            const response = await fetch(url, {
                headers: {
                    'X-Requested-With': 'XMLHttpRequest',
                },
                credentials: 'same-origin',
            });
            const payload = await response.json();
            if (!response.ok) {
                throw new Error(payload.error || 'Failed to load Zotero nodes.');
            }
            return payload.nodes || [];
        }

        function buildCollectionNode(node) {
            const item = document.createElement('li');
            const row = document.createElement('div');
            row.className = 'zotero-tree-row';

            const toggle = document.createElement('button');
            toggle.type = 'button';
            toggle.className = 'zotero-tree-toggle';
            toggle.textContent = '+';
            toggle.disabled = !node.has_children;

            const checkbox = document.createElement('input');
            checkbox.type = 'checkbox';
            checkbox.className = 'zotero-node-checkbox zotero-collection-checkbox';
            checkbox.dataset.nodeType = 'collection';
            checkbox.title = 'Select all items in this collection and all nested subcollections';

            const body = document.createElement('div');
            body.className = 'zotero-tree-content';
            body.innerHTML = `
                <strong>${escapeHtml(node.label)}</strong>
                <div class="zotero-tree-meta">${escapeHtml(node.child_collection_count || 0)} subcollections | ${escapeHtml(node.child_item_count || 0)} items</div>
            `;

            const children = document.createElement('ul');
            children.className = 'zotero-tree';
            children.hidden = true;

            collectionElements.set(node.key, {
                checkbox,
                children,
            });

            checkbox.addEventListener('change', function () {
                toggleCollectionSelection(node, checkbox);
            });

            let loaded = false;
            toggle.addEventListener('click', async function () {
                if (!node.has_children) {
                    return;
                }

                if (!loaded) {
                    const loadingRow = document.createElement('li');
                    loadingRow.innerHTML = '<div class="zotero-inline-spinner">Loading...</div>';
                    children.innerHTML = '';
                    children.appendChild(loadingRow);
                    children.hidden = false;
                    toggle.textContent = '-';
                    try {
                        const nodes = await loadChildren(node.key, node.hierarchy);
                        loadedChildren.set(node.key, nodes);
                        subtreeItemsCache.delete(node.key);
                        children.innerHTML = '';
                        if (!nodes.length) {
                            const emptyRow = document.createElement('li');
                            emptyRow.textContent = 'This collection is empty.';
                            children.appendChild(emptyRow);
                        } else {
                            children.appendChild(renderNodeList(nodes));
                        }
                        loaded = true;
                    } catch (error) {
                        children.innerHTML = `<li class="zotero-tree-meta">${escapeHtml(error.message)}</li>`;
                        showFeedback('error', error.message);
                    }
                    return;
                }

                children.hidden = !children.hidden;
                toggle.textContent = children.hidden ? '+' : '-';
            });

            row.appendChild(toggle);
            row.appendChild(checkbox);
            row.appendChild(body);
            item.appendChild(row);
            item.appendChild(children);
            return item;
        }

        async function renderRoot() {
            if (!configReady) {
                updateSelectedItemsView();
                return;
            }

            setTreeStatus('Loading top-level Zotero collections...', true);
            treeRoot.innerHTML = '';
            try {
                const nodes = await loadChildren('', 0);
                loadedChildren.set('__root__', nodes);
                const list = document.createElement('ul');
                list.className = 'zotero-tree';
                list.appendChild(renderNodeList(nodes));
                treeRoot.innerHTML = '';
                treeRoot.appendChild(list);
                setTreeStatus('', false);
            } catch (error) {
                setTreeStatus('', false);
                showFeedback('error', error.message);
            }
            updateSelectedItemsView();
        }

        importButton.addEventListener('click', async function () {
            const manuscriptUuid = manuscriptSelect.value;
            const queuedItems = Array.from(selectedItems.values()).map((item) => ({
                key: item.key,
                hierarchy: item.hierarchy,
            }));

            if (!manuscriptUuid) {
                showFeedback('error', 'Select a manuscript before importing.');
                return;
            }
            if (!queuedItems.length) {
                showFeedback('error', 'Select at least one Zotero item to import.');
                return;
            }

            importButton.disabled = true;
            showFeedback('info', 'Import in progress...');
            try {
                const response = await fetch(importUrl, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': getCsrfToken(),
                        'X-Requested-With': 'XMLHttpRequest',
                    },
                    credentials: 'same-origin',
                    body: JSON.stringify({
                        manuscript_uuid: manuscriptUuid,
                        selected_items: queuedItems,
                    }),
                });
                const payload = await response.json();
                if (!response.ok) {
                    throw new Error(payload.error || 'Import failed.');
                }

                showFeedback(
                    'success',
                    `Imported ${payload.selected_count} selected item(s): ${payload.bibliography_created} bibliography row(s) created, ${payload.bibliography_updated} updated, ${payload.links_created} manuscript link(s) created, ${payload.links_existing} already existed.`
                );
            } catch (error) {
                showFeedback('error', error.message);
            } finally {
                importButton.disabled = false;
            }
        });

        reloadButton.addEventListener('click', function () {
            loadedChildren.clear();
            subtreeItemsCache.clear();
            collectionElements.clear();
            renderRoot();
        });

        clearButton.addEventListener('click', function () {
            selectedItems.clear();
            document.querySelectorAll('#zotero-tree-root input[type="checkbox"]').forEach((checkbox) => {
                checkbox.checked = false;
                checkbox.indeterminate = false;
            });
            updateSelectedItemsView();
            showFeedback('info', 'Selection cleared.');
        });

        initializeManuscriptSelect();
        updateSelectedItemsView();
        renderRoot();
    });
})();