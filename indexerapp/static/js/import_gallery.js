/* import_gallery.js
   Upload images to manuscript, list gallery via /ms-gallery/, delete images.
   Inspired by existing importer.js usage.
*/

let gallerySelectedMs = null;
let galleryFiles = [];
let lightGalleryInstance = null;
let currentGalleryImages = [];
// pageRoot is defined globally in main.js

function import_gallery_init() {
    console.log("Initializing gallery importer...");
    // initialize select2 for manuscript selector
    $('.manuscript_filter').select2({
        ajax: {
            url: pageRoot+'/manuscripts-autocomplete/',
            dataType: 'json'
        },
        placeholder: 'Search for a manuscript...',
        allowClear: true
    });

    $('.manuscript_filter').on('select2:select', function(e) {
        gallerySelectedMs = e.params.data.id;
        loadGalleryForMs(gallerySelectedMs);
    });
    
    // Clear event
    $('.manuscript_filter').on('select2:unselect', function(e) {
        gallerySelectedMs = null;
        document.getElementById('lightgallery').innerHTML = '';
        if (lightGalleryInstance) {
            lightGalleryInstance.destroy();
            lightGalleryInstance = null;
        }
    });

    const drop = document.getElementById('drop-area');
    const fileInput = document.getElementById('file-input-gallery');

    if (drop) {
        drop.addEventListener('click', () => fileInput.click());
        drop.addEventListener('dragover', (e) => { 
            e.preventDefault(); 
            e.stopPropagation();
            drop.classList.add('bg-gray-100'); 
        });
        drop.addEventListener('dragleave', (e) => { 
            e.preventDefault(); 
            e.stopPropagation();
            drop.classList.remove('bg-gray-100'); 
        });
        drop.addEventListener('drop', handleDropGallery);
    }
    
    if (fileInput) {
        fileInput.addEventListener('change', handleFilesSelected);
    }

    const uploadBtn = document.getElementById('upload-btn');
    if (uploadBtn) uploadBtn.addEventListener('click', uploadSelectedFiles);
    
    const delBtn = document.getElementById('delete-selected-btn');
    if (delBtn) delBtn.addEventListener('click', deleteSelectedImage);
    
    const delAllBtn = document.getElementById('delete-all-btn');
    if (delAllBtn) delAllBtn.addEventListener('click', deleteAllImagesForMs);
}

function handleDropGallery(e) {
    e.preventDefault();
    e.stopPropagation();
    document.getElementById('drop-area').classList.remove('bg-gray-100');
    
    const dt = e.dataTransfer;
    const files = dt.files;
    handleFiles(files);
}

function handleFilesSelected(e) {
    handleFiles(e.target.files);
}

function handleFiles(fileList) {
    const previewContainer = document.getElementById('image-preview-container');
    const countLabel = document.getElementById('selection-count');
    
    for (let i = 0; i < fileList.length; i++) {
        const f = fileList[i];
        if (!f.type.match(/^image\/(jpeg|png)$/)) continue;
        galleryFiles.push(f);
        
        // Preview
        const reader = new FileReader();
        reader.onload = function(e) {
            const div = document.createElement('div');
            
            const img = document.createElement('img');
            img.src = e.target.result;
            img.style.height = '30px';
            img.style.width = 'auto';
            img.className = 'rounded shadow-sm border border-gray-300 object-cover';
            img.title = f.name;
            
            div.appendChild(img);
            if (previewContainer) previewContainer.appendChild(div);
        };
        reader.readAsDataURL(f);
    }
    
    if (countLabel) countLabel.innerText = galleryFiles.length + ' files selected';
    const status = document.getElementById('gallery-status');
    if (status) status.innerText = '';
}

function uploadSelectedFiles() {
    if (!gallerySelectedMs) { alert('Select manuscript first'); return; }
    if (galleryFiles.length === 0) { alert('No images selected'); return; }

    const csrfToken = getCookie('csrftoken');
    const form = new FormData();
    form.append('manuscript_id', gallerySelectedMs);
    
    for (let i = 0; i < galleryFiles.length; i++) {
        form.append('images', galleryFiles[i]);
    }

    const xhr = new XMLHttpRequest();
    xhr.open('POST', '/ms-gallery/', true);
    xhr.setRequestHeader('X-CSRFToken', csrfToken);

    // Progress bar
    const progressContainer = document.getElementById('progress-container');
    const progressBar = document.getElementById('upload-progress-bar');
    
    if (progressContainer) progressContainer.classList.remove('hidden');
    if (progressBar) {
        progressBar.style.width = '0%';
        progressBar.innerText = '0%';
    }

    xhr.upload.onprogress = function(e) {
        if (e.lengthComputable && progressBar) {
            const percentComplete = (e.loaded / e.total) * 100;
            progressBar.style.width = percentComplete + '%';
            progressBar.innerText = Math.round(percentComplete) + '%';
        }
    };

    xhr.onload = function() {
        if (xhr.status === 200) {
            const data = JSON.parse(xhr.responseText);
            const status = document.getElementById('gallery-status');
            if (status) status.innerText = 'Uploaded ' + (data.created ? data.created.length : 0) + ' images.';
            galleryFiles = []; // clear queue
            document.getElementById('image-preview-container').innerHTML = ''; // clear preview
            document.getElementById('selection-count').innerText = ''; // clear count
            loadGalleryForMs(gallerySelectedMs);
        } else {
            console.error(xhr.responseText);
            document.getElementById('gallery-status').innerText = 'Upload failed: ' + xhr.statusText;
        }
        setTimeout(() => {
            if (progressContainer) progressContainer.classList.add('hidden');
        }, 2000);
    };

    xhr.onerror = function() {
        document.getElementById('gallery-status').innerText = 'Upload error during network request.';
        if (progressContainer) progressContainer.classList.add('hidden');
    };

    xhr.send(form);
}

function loadGalleryForMs(msId) {
    if (!msId) return;
    const container = document.getElementById('lightgallery');
    if (!container) return;
    
    container.innerHTML = 'Loading...';
    
    // Destroy previous instance
    if (lightGalleryInstance) {
        lightGalleryInstance.destroy();
        lightGalleryInstance = null;
    }

    fetch(`/ms-gallery/?manuscript_id=${msId}`)
    .then(r => r.json())
    .then(data => {
        container.innerHTML = '';
        if (!data.images || data.images.length === 0) {
            container.innerHTML = '<p class="text-gray-500 col-span-full text-center">No images found for this manuscript.</p>';
            return;
        }

        currentGalleryImages = data.images;

        const dynamicEl = data.images.map(item => ({
            id: item.id, // Store ID directly
            src: item.image_url,
            thumb: item.thumbnail_url || item.image_url,
            subHtml: `<h4>${escapeHtml(item.name || 'Image')}</h4>`,
            // Custom attribute for identification if needed
            imageId: item.id
        }));

        // Inline gallery configuration
        lightGalleryInstance = lightGallery(container, {
            container: container,
            dynamic: true,
            dynamicEl: dynamicEl,
            hash: false,
            closable: false,
            showMaximizeIcon: true,
            appendSubHtmlTo: '.lg-item',
            slideDelay: 400,
            plugins: [lgZoom, lgThumbnail],
            thumbnail: true,
            zoom: true,
            autoplay: false,
        });

        // Open gallery automatically in inline mode
        lightGalleryInstance.openGallery();

    })
    .catch(e => {
        console.error(e);
        container.innerHTML = 'Error loading gallery.';
    });
}

function deleteSelectedImage() {
    if (!lightGalleryInstance) { alert('Gallery not loaded'); return; }
    
    // lightGalleryInstance.index is the current slide index
    const index = lightGalleryInstance.index;
    if (typeof index === 'undefined' || index < 0 || !currentGalleryImages[index]) {
        alert('No image selected');
        return;
    }
    
    const image_id = currentGalleryImages[index].id;

    if (!confirm('Delete currently viewed image?')) return;

    const csrfToken = getCookie('csrftoken');
    fetch('/ms-gallery/', { 
        method: 'DELETE', 
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrfToken
        }, 
        body: JSON.stringify({ manuscript_id: gallerySelectedMs, image_id: image_id }) 
    })
    .then(r => r.json())
    .then(data => { 
        document.getElementById('gallery-status').innerText = 'Deleted image ' + image_id; 
        loadGalleryForMs(gallerySelectedMs); 
    })
    .catch(e => console.error(e));
}

function deleteAllImagesForMs() {
    if (!gallerySelectedMs) { alert('Select manuscript first'); return; }
    if (!confirm('Are you sure you want to delete ALL images for this manuscript? This cannot be undone.')) return;

    const csrfToken = getCookie('csrftoken');
    
    fetch('/ms-gallery/', { 
        method: 'DELETE', 
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrfToken
        }, 
        body: JSON.stringify({manuscript_id: gallerySelectedMs}) 
    })
    .then(r => r.json())
    .then(data => { 
        document.getElementById('gallery-status').innerText = 'Deleted all images.'; 
        loadGalleryForMs(gallerySelectedMs); 
    })
    .catch(e => console.error(e));
}

function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

function escapeHtml(s) {
    return s ? s.replace(/[&<>"']/g, function(m) {
        return {
            '&': '&amp;',
            '<': '&lt;',
            '>': '&gt;',
            '"': '&quot;',
            "'": '&#039;'
        }[m];
    }) : '';
}

// Global exposure for Alpine x-init
window.import_gallery_init = import_gallery_init;
