/**
 * MonoClaw Legal Dashboard — Client-side utilities
 * Works with htmx, Alpine.js, and Chart.js for reactive UI updates.
 */

// -- Activity feed badge polling ------------------------------------------
document.addEventListener('htmx:afterSwap', function(evt) {
    if (evt.detail.target.id === 'activity-feed') {
        var badge = document.getElementById('activity-badge');
        var items = evt.detail.target.querySelectorAll('[data-requires-action="true"]');
        if (items.length > 0) {
            badge.textContent = items.length;
            badge.classList.remove('hidden');
        } else {
            badge.classList.add('hidden');
        }
    }
});

// -- Chart.js defaults ----------------------------------------------------
if (typeof Chart !== 'undefined') {
    Chart.defaults.color = '#9ca3af';
    Chart.defaults.borderColor = '#2d3352';
    Chart.defaults.font.family = "'Inter', system-ui, sans-serif";
}

// -- Date/time formatters -------------------------------------------------
function formatDate(dateStr) {
    var d = new Date(dateStr);
    return d.toLocaleDateString('en-HK', { year: 'numeric', month: 'short', day: 'numeric' });
}

function formatTime(timeStr) {
    if (timeStr && timeStr.length === 5) return timeStr;
    var d = new Date(timeStr);
    return d.toLocaleTimeString('en-HK', { hour: '2-digit', minute: '2-digit' });
}

// -- Deadline countdown ---------------------------------------------------
function updateCountdowns() {
    document.querySelectorAll('[data-deadline]').forEach(function(el) {
        var deadline = new Date(el.dataset.deadline);
        var now = new Date();
        var diff = deadline - now;
        var days = Math.ceil(diff / (1000 * 60 * 60 * 24));

        if (days < 0) {
            el.textContent = Math.abs(days) + ' days overdue';
            el.className = 'countdown-critical';
        } else if (days === 0) {
            el.textContent = 'Due today';
            el.className = 'countdown-critical';
        } else if (days <= 3) {
            el.textContent = days + ' day' + (days > 1 ? 's' : '') + ' left';
            el.className = 'text-red-400 font-semibold';
        } else if (days <= 7) {
            el.textContent = days + ' days left';
            el.className = 'text-amber-400';
        } else {
            el.textContent = days + ' days left';
            el.className = 'text-gray-400';
        }
    });
}

setInterval(updateCountdowns, 60000);
document.addEventListener('DOMContentLoaded', updateCountdowns);
document.addEventListener('htmx:afterSwap', updateCountdowns);

// -- File upload drag-and-drop --------------------------------------------
function initUploadZone(zoneId, inputId) {
    var zone = document.getElementById(zoneId);
    var input = document.getElementById(inputId);
    if (!zone || !input) return;

    zone.addEventListener('click', function() { input.click(); });
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
        input.files = e.dataTransfer.files;
        if (input.form) htmx.trigger(input.form, 'submit');
    });
}

// -- Anomaly score colour -------------------------------------------------
function anomalyClass(score) {
    if (score >= 0.7) return 'anomaly-flagged';
    if (score >= 0.4) return 'anomaly-unusual';
    return 'anomaly-standard';
}

// -- Confirmation dialog --------------------------------------------------
function confirmAction(message) {
    return window.confirm(message);
}

// -- Batch selection helper -----------------------------------------------
function toggleBatchSelect(checkbox) {
    var checkboxes = document.querySelectorAll('.batch-checkbox');
    checkboxes.forEach(function(cb) { cb.checked = checkbox.checked; });
}
