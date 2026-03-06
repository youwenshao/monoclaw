/**
 * MonoClaw Immigration Dashboard — Client-side utilities
 * Works with htmx and Alpine.js for reactive UI updates.
 */

// ── Activity feed badge polling ──────────────────────────────────
document.addEventListener('htmx:afterSwap', function(evt) {
    if (evt.detail.target.id === 'activity-feed') {
        const badge = document.getElementById('activity-badge');
        const items = evt.detail.target.querySelectorAll('[data-requires-action="true"]');
        if (items.length > 0) {
            badge.textContent = items.length;
            badge.classList.remove('hidden');
        } else {
            badge.classList.add('hidden');
        }
    }
});

// ── Chart.js defaults ────────────────────────────────────────────
if (typeof Chart !== 'undefined') {
    Chart.defaults.color = '#9ca3af';
    Chart.defaults.borderColor = '#2d3352';
    Chart.defaults.font.family = "'Inter', system-ui, sans-serif";
}

// ── Dropzone helper ──────────────────────────────────────────────
function initDropzone(elementId, uploadUrl) {
    const zone = document.getElementById(elementId);
    if (!zone) return;

    zone.addEventListener('dragover', function(e) {
        e.preventDefault();
        zone.classList.add('dragover');
    });
    zone.addEventListener('dragleave', function() {
        zone.classList.remove('dragover');
    });
    zone.addEventListener('drop', function(e) {
        e.preventDefault();
        zone.classList.remove('dragover');
        if (e.dataTransfer.files.length > 0) {
            uploadFiles(e.dataTransfer.files, uploadUrl);
        }
    });

    const fileInput = zone.querySelector('input[type="file"]');
    if (fileInput) {
        fileInput.addEventListener('change', function() {
            if (fileInput.files.length > 0) {
                uploadFiles(fileInput.files, uploadUrl);
            }
        });
    }
}

async function uploadFiles(files, uploadUrl) {
    for (const file of files) {
        const formData = new FormData();
        formData.append('file', file);

        const queue = document.getElementById('upload-queue');
        if (queue) {
            const item = document.createElement('div');
            item.className = 'flex items-center gap-3 p-3 bg-navy-800 rounded-lg';
            item.innerHTML = `
                <svg class="animate-spin w-4 h-4 text-gold-400" fill="none" viewBox="0 0 24 24">
                    <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                    <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"></path>
                </svg>
                <span class="text-sm">${file.name}</span>
                <span class="ml-auto text-xs text-gray-400">Uploading...</span>
            `;
            queue.prepend(item);
        }

        try {
            const response = await fetch(uploadUrl, { method: 'POST', body: formData });
            const data = await response.json();
            htmx.trigger(document.body, 'documentUploaded', { detail: data });
        } catch (err) {
            console.error('Upload failed:', err);
        }
    }
}

// ── Confidence color helper ──────────────────────────────────────
function confidenceClass(score) {
    if (score >= 0.85) return 'confidence-high';
    if (score >= 0.70) return 'confidence-medium';
    return 'confidence-low';
}

function confidenceBadge(score) {
    if (score >= 0.85) return 'badge-green';
    if (score >= 0.70) return 'badge-amber';
    return 'badge-red';
}

// ── Status badge helper ──────────────────────────────────────────
function statusBadge(status) {
    const map = {
        'documents_gathering': 'badge-grey',
        'application_submitted': 'badge-blue',
        'acknowledgement_received': 'badge-blue',
        'additional_documents_requested': 'badge-amber',
        'under_processing': 'badge-amber',
        'approval_in_principle': 'badge-green',
        'visa_label_issued': 'badge-green',
        'entry_made': 'badge-green',
        'hkid_applied': 'badge-green',
        'rejected': 'badge-red',
    };
    return map[status] || 'badge-grey';
}

function statusLabel(status) {
    return status.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
}

// ── Date formatter ───────────────────────────────────────────────
function formatDate(dateStr) {
    if (!dateStr) return '';
    const d = new Date(dateStr);
    return d.toLocaleDateString('en-HK', { year: 'numeric', month: 'short', day: 'numeric' });
}

function formatTime(dateStr) {
    if (!dateStr) return '';
    const d = new Date(dateStr);
    return d.toLocaleTimeString('en-HK', { hour: '2-digit', minute: '2-digit' });
}

// ── Confirmation dialog ──────────────────────────────────────────
function confirmAction(message) {
    return window.confirm(message);
}
