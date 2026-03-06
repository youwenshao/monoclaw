/* Academic Dashboard — client-side utilities */

document.addEventListener('DOMContentLoaded', function () {
    // Poll activity feed badge count
    function updateBadge() {
        fetch('/api/events?limit=50')
            .then(r => r.json())
            .then(events => {
                const unack = events.filter(e => !e.acknowledged).length;
                const badge = document.getElementById('activity-badge');
                if (badge) {
                    badge.textContent = unack;
                    badge.classList.toggle('hidden', unack === 0);
                }
            })
            .catch(() => {});
    }
    updateBadge();
    setInterval(updateBadge, 10000);

    // Global htmx error handler
    document.body.addEventListener('htmx:responseError', function (evt) {
        console.error('HTMX error:', evt.detail);
    });
});

/* Clipboard copy helper */
function copyToClipboard(text, btn) {
    navigator.clipboard.writeText(text).then(() => {
        const original = btn.textContent;
        btn.textContent = 'Copied!';
        setTimeout(() => { btn.textContent = original; }, 1500);
    });
}

/* Knowledge graph rendering with vis.js */
function renderKnowledgeGraph(containerId, data) {
    const nodes = new vis.DataSet(data.nodes || []);
    const edges = new vis.DataSet(data.edges || []);
    const container = document.getElementById(containerId);
    if (!container) return;

    new vis.Network(container, { nodes, edges }, {
        nodes: {
            shape: 'dot',
            size: 16,
            font: { color: '#e5e7eb', size: 12 },
            color: { background: '#d4a843', border: '#b8922f' },
        },
        edges: {
            color: { color: '#4b5563' },
            arrows: { to: { enabled: true, scaleFactor: 0.5 } },
            font: { color: '#9ca3af', size: 10 },
        },
        physics: { stabilization: { iterations: 100 } },
        interaction: { hover: true },
    });
}
