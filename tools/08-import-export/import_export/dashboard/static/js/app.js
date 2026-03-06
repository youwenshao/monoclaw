/**
 * MonoClaw Import/Export Dashboard — Client-side utilities
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

// ── Status badge helpers ─────────────────────────────────────────
function statusBadge(status) {
    const map = {
        'draft': 'badge-grey',
        'filed': 'badge-blue',
        'accepted': 'badge-green',
        'rejected': 'badge-red',
        'amended': 'badge-amber',
        'sent': 'badge-blue',
        'partially_paid': 'badge-amber',
        'paid': 'badge-green',
        'overdue': 'badge-red',
        'cancelled': 'badge-grey',
        'not_started': 'badge-grey',
        'in_production': 'badge-blue',
        'qc_pending': 'badge-amber',
        'qc_passed': 'badge-green',
        'shipping': 'badge-blue',
        'delivered': 'badge-green',
        'completed': 'badge-green',
        'matched': 'badge-green',
        'shortage': 'badge-red',
        'overage': 'badge-amber',
        'damaged': 'badge-red',
        'in_transit': 'badge-blue',
        'arrived': 'badge-blue',
        'at_warehouse': 'badge-amber',
        'reconciled': 'badge-green',
        'closed': 'badge-grey',
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

function formatCurrency(amount, currency) {
    if (amount == null) return '';
    const symbols = { HKD: 'HK$', USD: 'US$', EUR: '€', GBP: '£', JPY: '¥', CNH: '¥' };
    const sym = symbols[currency] || currency + ' ';
    return sym + Number(amount).toLocaleString('en-HK', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

// ── Confirmation dialog ──────────────────────────────────────────
function confirmAction(message) {
    return window.confirm(message);
}
