/**
 * MonoClaw Student Dashboard — Client-side utilities
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
        zone.classList.add('border-gold-500');
    });
    zone.addEventListener('dragleave', function() {
        zone.classList.remove('border-gold-500');
    });
    zone.addEventListener('drop', function(e) {
        e.preventDefault();
        zone.classList.remove('border-gold-500');
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

// ── Code editor (CodeMirror wrapper) ─────────────────────────────
function initCodeEditor(elementId, language) {
    const textarea = document.getElementById(elementId);
    if (!textarea || typeof CodeMirror === 'undefined') return null;

    const modeMap = { python: 'python', javascript: 'javascript' };
    return CodeMirror.fromTextArea(textarea, {
        mode: modeMap[language] || 'python',
        theme: 'material-darker',
        lineNumbers: true,
        indentUnit: 4,
        tabSize: 4,
        indentWithTabs: false,
        matchBrackets: true,
        autoCloseBrackets: true,
        lineWrapping: true,
    });
}

// ── Kanban drag-and-drop (SortableJS wrapper) ────────────────────
function initKanban() {
    document.querySelectorAll('.kanban-column .kanban-cards').forEach(function(column) {
        new Sortable(column, {
            group: 'kanban',
            animation: 150,
            ghostClass: 'sortable-ghost',
            onEnd: function(evt) {
                const appId = evt.item.dataset.applicationId;
                const newStage = evt.to.dataset.stage;
                if (appId && newStage) {
                    fetch(`/job-tracker/applications/${appId}/stage`, {
                        method: 'PUT',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ stage: newStage }),
                    });
                }
            },
        });
    });
}

// ── Exam timer ───────────────────────────────────────────────────
function startExamTimer(durationMinutes, onTick, onExpire) {
    let remaining = durationMinutes * 60;
    const total = remaining;

    const interval = setInterval(function() {
        remaining--;
        const pct = (remaining / total) * 100;
        if (onTick) onTick(remaining, pct);

        if (remaining <= 600 && remaining > 120) {
            document.querySelector('.timer-bar')?.classList.add('warning');
        } else if (remaining <= 120) {
            document.querySelector('.timer-bar')?.classList.add('danger');
        }

        if (remaining <= 0) {
            clearInterval(interval);
            if (onExpire) onExpire();
        }
    }, 1000);

    return interval;
}

function formatTimer(seconds) {
    const m = Math.floor(seconds / 60);
    const s = seconds % 60;
    return `${m}:${s.toString().padStart(2, '0')}`;
}

// ── Flashcard flip ───────────────────────────────────────────────
function flipCard(el) {
    el.closest('.flashcard').classList.toggle('flipped');
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

// ── Match score color ────────────────────────────────────────────
function matchScoreClass(score) {
    if (score >= 0.8) return 'text-green-400';
    if (score >= 0.6) return 'text-amber-400';
    return 'text-red-400';
}

// ── Confirmation dialog ──────────────────────────────────────────
function confirmAction(message) {
    return window.confirm(message);
}

// ── Status label formatter ───────────────────────────────────────
function statusLabel(status) {
    return status.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
}
