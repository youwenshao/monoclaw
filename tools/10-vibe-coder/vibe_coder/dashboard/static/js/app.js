/**
 * MonoClaw Vibe Coder Dashboard — Client-side utilities
 * Works with htmx, Alpine.js, and Monaco Editor for reactive developer UI.
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

// -- Monaco Editor initialization -----------------------------------------
let monacoEditor = null;

function initMonacoEditor(containerId, options) {
    const defaults = {
        language: 'python',
        theme: 'vs-dark',
        minimap: { enabled: false },
        fontSize: 14,
        fontFamily: "'JetBrains Mono', monospace",
        lineNumbers: 'on',
        scrollBeyondLastLine: false,
        automaticLayout: true,
        tabSize: 4,
    };
    const merged = Object.assign({}, defaults, options || {});

    require.config({ paths: { vs: 'https://cdn.jsdelivr.net/npm/monaco-editor@0.45.0/min/vs' }});
    require(['vs/editor/editor.main'], function() {
        monaco.editor.defineTheme('monoclaw-dark', {
            base: 'vs-dark',
            inherit: true,
            rules: [],
            colors: {
                'editor.background': '#222744',
                'editor.foreground': '#f3f4f6',
                'editorLineNumber.foreground': '#6b7280',
                'editor.selectionBackground': '#363b5a',
                'editor.lineHighlightBackground': '#2d3352',
            },
        });
        merged.theme = 'monoclaw-dark';

        const container = document.getElementById(containerId);
        if (container) {
            monacoEditor = monaco.editor.create(container, merged);
        }
    });
}

function getEditorContent() {
    return monacoEditor ? monacoEditor.getValue() : '';
}

function setEditorContent(content) {
    if (monacoEditor) monacoEditor.setValue(content);
}

function getEditorSelection() {
    if (!monacoEditor) return '';
    const sel = monacoEditor.getSelection();
    return monacoEditor.getModel().getValueInRange(sel);
}

// -- SSE streaming helper -------------------------------------------------
function streamToElement(url, body, targetId, options) {
    const target = document.getElementById(targetId);
    if (!target) return;

    const defaults = { method: 'POST', append: false, onDone: null };
    const opts = Object.assign({}, defaults, options || {});

    if (!opts.append) target.textContent = '';

    fetch(url, {
        method: opts.method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
    }).then(function(response) {
        const reader = response.body.getReader();
        const decoder = new TextDecoder();

        function read() {
            reader.read().then(function(result) {
                if (result.done) {
                    if (opts.onDone) opts.onDone();
                    return;
                }
                const text = decoder.decode(result.value, { stream: true });
                const lines = text.split('\n');
                for (const line of lines) {
                    if (line.startsWith('data: ')) {
                        const data = line.slice(6);
                        if (data === '[DONE]') {
                            if (opts.onDone) opts.onDone();
                            return;
                        }
                        try {
                            const parsed = JSON.parse(data);
                            if (parsed.token) target.textContent += parsed.token;
                        } catch (e) {
                            target.textContent += data;
                        }
                    }
                }
                read();
            });
        }
        read();
    });
}

// -- Code language detection -----------------------------------------------
function detectLanguage(code) {
    if (/^(import |from |def |class |async def )/.test(code)) return 'python';
    if (/^(const |let |var |function |import |export |=>)/.test(code)) return 'javascript';
    if (/^(interface |type |enum |namespace )/.test(code)) return 'typescript';
    if (/^(package |func |type |import \()/.test(code)) return 'go';
    if (/^(fn |use |mod |struct |impl )/.test(code)) return 'rust';
    return 'plaintext';
}

// -- Copy to clipboard ----------------------------------------------------
function copyToClipboard(text, buttonEl) {
    navigator.clipboard.writeText(text).then(function() {
        if (buttonEl) {
            const orig = buttonEl.textContent;
            buttonEl.textContent = 'Copied!';
            setTimeout(function() { buttonEl.textContent = orig; }, 1500);
        }
    });
}

// -- Date formatter -------------------------------------------------------
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

// -- Status helpers -------------------------------------------------------
function statusBadge(status) {
    const map = {
        'pending': 'badge-grey',
        'processing': 'badge-amber',
        'completed': 'badge-green',
        'error': 'badge-red',
        'stale': 'badge-amber',
        'fresh': 'badge-green',
    };
    return map[status] || 'badge-grey';
}

function statusLabel(status) {
    return status.replace(/_/g, ' ').replace(/\b\w/g, function(c) { return c.toUpperCase(); });
}

// -- Confirmation dialog --------------------------------------------------
function confirmAction(message) {
    return window.confirm(message);
}
