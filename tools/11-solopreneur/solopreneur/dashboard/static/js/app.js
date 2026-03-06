/**
 * Solopreneur Dashboard — Client-side JavaScript
 */

document.addEventListener('DOMContentLoaded', function () {
    pollActivityBadge();
    setInterval(pollActivityBadge, 15000);
});

function pollActivityBadge() {
    fetch('/api/events?limit=10&unacknowledged=1')
        .then(function (r) { return r.json(); })
        .then(function (events) {
            var badge = document.getElementById('activity-badge');
            if (!badge) return;
            if (events && events.length > 0) {
                badge.textContent = events.length;
                badge.classList.remove('hidden');
            } else {
                badge.classList.add('hidden');
            }
        })
        .catch(function () {});
}

function acknowledgeEvent(eventId) {
    fetch('/api/events/' + eventId + '/acknowledge')
        .then(function () {
            var el = document.getElementById('event-' + eventId);
            if (el) el.remove();
            pollActivityBadge();
        })
        .catch(function () {});
}

function formatCurrency(amount, currency) {
    currency = currency || 'HKD';
    return new Intl.NumberFormat('en-HK', {
        style: 'currency',
        currency: currency,
        minimumFractionDigits: 2
    }).format(amount);
}

function formatDate(dateStr) {
    if (!dateStr) return '';
    var d = new Date(dateStr);
    var dd = String(d.getDate()).padStart(2, '0');
    var mm = String(d.getMonth() + 1).padStart(2, '0');
    var yyyy = d.getFullYear();
    return dd + '/' + mm + '/' + yyyy;
}
