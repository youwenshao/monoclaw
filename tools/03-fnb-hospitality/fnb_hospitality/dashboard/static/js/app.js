/**
 * MonoClaw F&B Hospitality Dashboard — Client-side utilities
 * Works with htmx, Alpine.js, Chart.js, and SSE for reactive UI updates.
 */

// -- Activity feed badge polling ------------------------------------------
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

// -- Chart.js defaults ----------------------------------------------------
if (typeof Chart !== 'undefined') {
    Chart.defaults.color = '#9ca3af';
    Chart.defaults.borderColor = '#2d3352';
    Chart.defaults.font.family = "'Inter', system-ui, sans-serif";
}

// -- Date/time formatters -------------------------------------------------
function formatDate(dateStr) {
    const d = new Date(dateStr);
    return d.toLocaleDateString('en-HK', { year: 'numeric', month: 'short', day: 'numeric' });
}

function formatTime(timeStr) {
    if (timeStr && timeStr.length === 5) return timeStr;
    const d = new Date(timeStr);
    return d.toLocaleTimeString('en-HK', { hour: '2-digit', minute: '2-digit' });
}

function formatHKPhone(phone) {
    if (!phone) return '';
    const digits = phone.replace(/\D/g, '');
    if (digits.length === 11 && digits.startsWith('852')) {
        const local = digits.slice(3);
        return '+852 ' + local.slice(0, 4) + ' ' + local.slice(4);
    }
    return phone;
}

// -- SSE helpers for QueueBot live updates --------------------------------
function initSSE(url, onMessage) {
    const source = new EventSource(url);
    source.onmessage = function(event) {
        try {
            const data = JSON.parse(event.data);
            onMessage(data);
        } catch (e) {
            onMessage(event.data);
        }
    };
    source.onerror = function() {
        setTimeout(function() { initSSE(url, onMessage); }, 5000);
    };
    return source;
}

// -- Heatmap builder (booking density) ------------------------------------
function buildHeatmap(canvasId, data, labels) {
    const ctx = document.getElementById(canvasId);
    if (!ctx) return null;

    const maxVal = Math.max(...data.flat(), 1);

    return new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels.hours || [],
            datasets: (labels.days || []).map(function(day, i) {
                return {
                    label: day,
                    data: data[i] || [],
                    backgroundColor: 'rgba(212, 168, 67, ' + (0.3 + 0.7 * (i / 7)) + ')',
                };
            }),
        },
        options: {
            responsive: true,
            scales: {
                y: { beginAtZero: true, title: { display: true, text: 'Bookings' } },
            },
        },
    });
}

// -- Floor plan table click handler ---------------------------------------
function onTableClick(tableId) {
    htmx.ajax('GET', '/table-master/partials/table-detail/' + tableId, {
        target: '#table-detail-panel',
        swap: 'innerHTML',
    });
}

// -- Confirmation dialog --------------------------------------------------
function confirmAction(message) {
    return window.confirm(message);
}

// -- Queue number display animation ---------------------------------------
function animateQueueNumber(elementId, targetNumber) {
    const el = document.getElementById(elementId);
    if (!el) return;
    let current = 0;
    const step = Math.ceil(targetNumber / 20);
    const interval = setInterval(function() {
        current = Math.min(current + step, targetNumber);
        el.textContent = '#' + current;
        if (current >= targetNumber) clearInterval(interval);
    }, 50);
}
