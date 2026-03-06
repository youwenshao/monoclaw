/**
 * MonoClaw Real Estate Dashboard — Client-side utilities
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
function initDropzone(elementId, onFiles) {
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
            onFiles(e.dataTransfer.files);
        }
    });
}

// ── Format HKD currency ─────────────────────────────────────────
function formatHKD(amount) {
    if (amount >= 10000000) {
        return 'HK$' + (amount / 10000000).toFixed(1) + 'M';
    }
    return 'HK$' + amount.toLocaleString();
}

// ── Format Chinese price ─────────────────────────────────────────
function formatHKDChinese(amount) {
    if (amount >= 10000) {
        return '$' + (amount / 10000).toFixed(0) + '萬';
    }
    return '$' + amount.toLocaleString();
}

// ── Date formatter ───────────────────────────────────────────────
function formatDate(dateStr) {
    const d = new Date(dateStr);
    return d.toLocaleDateString('en-HK', { year: 'numeric', month: 'short', day: 'numeric' });
}

function formatTime(dateStr) {
    const d = new Date(dateStr);
    return d.toLocaleTimeString('en-HK', { hour: '2-digit', minute: '2-digit' });
}

// ── SSE chat helper ──────────────────────────────────────────────
function initChatStream(formId, outputId, endpoint) {
    const form = document.getElementById(formId);
    const output = document.getElementById(outputId);
    if (!form || !output) return;

    form.addEventListener('submit', async function(e) {
        e.preventDefault();
        const formData = new FormData(form);
        const query = formData.get('query');
        if (!query) return;

        output.innerHTML += '<div class="mb-2"><span class="text-gold-400 font-medium">You:</span> ' + query + '</div>';
        output.innerHTML += '<div class="mb-2" id="stream-response"><span class="text-green-400 font-medium">Mona:</span> <span id="stream-text"></span></div>';
        form.reset();

        const response = await fetch(endpoint, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ query: query }),
        });

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        const textEl = document.getElementById('stream-text');

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            textEl.textContent += decoder.decode(value);
            output.scrollTop = output.scrollHeight;
        }
    });
}

// ── Confirmation dialog ──────────────────────────────────────────
function confirmAction(message) {
    return window.confirm(message);
}
