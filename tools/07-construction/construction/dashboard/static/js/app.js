/**
 * MonoClaw Construction Dashboard — Client-side utilities
 */

// -- Activity feed badge polling --
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

// -- Chart.js defaults --
if (typeof Chart !== 'undefined') {
    Chart.defaults.color = '#9ca3af';
    Chart.defaults.borderColor = '#2d3352';
    Chart.defaults.font.family = "'Inter', system-ui, sans-serif";
}

// -- Status badge helpers --
function statusBadge(status) {
    const map = {
        'Received': 'badge-blue',
        'Under Examination': 'badge-amber',
        'Amendments Required': 'badge-red',
        'Approved': 'badge-green',
        'Consent Issued': 'badge-green',
        'reported': 'badge-blue',
        'assessed': 'badge-amber',
        'work_ordered': 'badge-amber',
        'in_progress': 'badge-amber',
        'completed': 'badge-green',
        'closed': 'badge-grey',
        'scheduled': 'badge-blue',
        'dispatched': 'badge-purple',
        'cancelled': 'badge-red',
        'rescheduled': 'badge-amber',
    };
    return map[status] || 'badge-grey';
}

function statusLabel(status) {
    return status.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
}

// -- Trade color helper --
function tradeColor(trade) {
    const map = {
        'demolition': '#6b7280', 'formwork': '#92400e', 'rebar': '#7c3aed',
        'concreting': '#6b7280', 'plumbing': '#2563eb', 'electrical': '#f59e0b',
        'HVAC': '#06b6d4', 'fire_services': '#ef4444', 'plastering': '#a78bfa',
        'tiling': '#14b8a6', 'painting': '#f97316', 'carpentry': '#a16207',
        'glazing': '#60a5fa', 'waterproofing': '#0891b2', 'landscaping': '#22c55e',
    };
    return map[trade] || '#9ca3af';
}

// -- Date formatter --
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

// -- Days elapsed calculator --
function daysElapsed(dateStr) {
    if (!dateStr) return 0;
    const start = new Date(dateStr);
    const now = new Date();
    return Math.floor((now - start) / (1000 * 60 * 60 * 24));
}

// -- Dropzone helper --
function initDropzone(elementId, uploadUrl) {
    const zone = document.getElementById(elementId);
    if (!zone) return;

    zone.addEventListener('dragover', function(e) { e.preventDefault(); zone.classList.add('dragover'); });
    zone.addEventListener('dragleave', function() { zone.classList.remove('dragover'); });
    zone.addEventListener('drop', function(e) {
        e.preventDefault();
        zone.classList.remove('dragover');
        if (e.dataTransfer.files.length > 0) uploadFiles(e.dataTransfer.files, uploadUrl);
    });

    const fileInput = zone.querySelector('input[type="file"]');
    if (fileInput) {
        fileInput.addEventListener('change', function() {
            if (fileInput.files.length > 0) uploadFiles(fileInput.files, uploadUrl);
        });
    }
}

async function uploadFiles(files, uploadUrl) {
    for (const file of files) {
        const formData = new FormData();
        formData.append('file', file);
        try {
            const response = await fetch(uploadUrl, { method: 'POST', body: formData });
            const data = await response.json();
            htmx.trigger(document.body, 'documentUploaded', { detail: data });
        } catch (err) {
            console.error('Upload failed:', err);
        }
    }
}

// -- Confirmation dialog --
function confirmAction(message) {
    return window.confirm(message);
}
