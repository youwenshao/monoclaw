/**
 * MonoClaw Accounting Dashboard — Client-side utilities
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
        'pending_review': 'badge-amber',
        'approved': 'badge-green',
        'pushed': 'badge-blue',
        'rejected': 'badge-red',
        'matched': 'badge-green',
        'unmatched': 'badge-red',
        'in_progress': 'badge-amber',
        'completed': 'badge-green',
        'not_started': 'badge-grey',
        'filed': 'badge-green',
        'overdue': 'badge-red',
        'settled': 'badge-green',
        'open': 'badge-amber',
    };
    return map[status] || 'badge-grey';
}

function statusLabel(status) {
    return status.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
}

// ── Currency formatter ───────────────────────────────────────────
function formatCurrency(amount, currency) {
    currency = currency || 'HKD';
    return new Intl.NumberFormat('en-HK', {
        style: 'currency',
        currency: currency,
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
    }).format(amount);
}

function formatHKD(amount) {
    return formatCurrency(amount, 'HKD');
}

// ── Exchange rate display ────────────────────────────────────────
function formatRate(rate, decimals) {
    decimals = decimals || 4;
    return Number(rate).toFixed(decimals);
}

function rateChangeClass(change) {
    if (change > 0) return 'text-green-400';
    if (change < 0) return 'text-red-400';
    return 'text-gray-400';
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

// ── Countdown helper ─────────────────────────────────────────────
function daysUntil(dateStr) {
    if (!dateStr) return null;
    const target = new Date(dateStr);
    const now = new Date();
    target.setHours(0, 0, 0, 0);
    now.setHours(0, 0, 0, 0);
    return Math.ceil((target - now) / (1000 * 60 * 60 * 24));
}

function deadlineUrgency(daysRemaining) {
    if (daysRemaining < 0) return 'badge-red';
    if (daysRemaining <= 7) return 'badge-red';
    if (daysRemaining <= 30) return 'badge-amber';
    return 'badge-green';
}

// ── Confirmation dialog ──────────────────────────────────────────
function confirmAction(message) {
    return window.confirm(message);
}
