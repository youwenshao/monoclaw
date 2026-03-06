/**
 * MonoClaw Medical-Dental Dashboard — Client-side utilities
 * Works with htmx, Alpine.js, Chart.js, and SSE for reactive UI updates.
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

function formatHKPhone(phone) {
    if (!phone) return '';
    var digits = phone.replace(/\D/g, '');
    if (digits.length === 11 && digits.startsWith('852')) {
        var local = digits.slice(3);
        return '+852 ' + local.slice(0, 4) + ' ' + local.slice(4);
    }
    return phone;
}

// -- SSE helpers for real-time transcription / queue updates ---------------
function initSSE(url, onMessage) {
    var source = new EventSource(url);
    source.onmessage = function(event) {
        try {
            var data = JSON.parse(event.data);
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

// -- Audio recording helpers (ScribeAI) -----------------------------------
var _mediaRecorder = null;
var _audioChunks = [];

function startRecording(onChunk) {
    navigator.mediaDevices.getUserMedia({ audio: true }).then(function(stream) {
        _mediaRecorder = new MediaRecorder(stream, { mimeType: 'audio/webm' });
        _audioChunks = [];
        _mediaRecorder.ondataavailable = function(e) {
            _audioChunks.push(e.data);
            if (onChunk) onChunk(e.data);
        };
        _mediaRecorder.start(30000);
    });
}

function stopRecording() {
    return new Promise(function(resolve) {
        if (!_mediaRecorder || _mediaRecorder.state === 'inactive') {
            resolve(null);
            return;
        }
        _mediaRecorder.onstop = function() {
            var blob = new Blob(_audioChunks, { type: 'audio/webm' });
            _mediaRecorder.stream.getTracks().forEach(function(t) { t.stop(); });
            _mediaRecorder = null;
            resolve(blob);
        };
        _mediaRecorder.stop();
    });
}

// -- Compliance chart builder (MedReminder) -------------------------------
function buildComplianceChart(canvasId, labels, data) {
    var ctx = document.getElementById(canvasId);
    if (!ctx) return null;

    return new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [{
                label: 'Compliance %',
                data: data,
                borderColor: '#d4a843',
                backgroundColor: 'rgba(212, 168, 67, 0.1)',
                fill: true,
                tension: 0.3,
            }],
        },
        options: {
            responsive: true,
            scales: {
                y: { beginAtZero: true, max: 100, title: { display: true, text: '%' } },
            },
        },
    });
}

// -- Schedule grid helpers (ClinicScheduler) ------------------------------
function buildScheduleGrid(canvasId, doctors, timeSlots, appointments) {
    var ctx = document.getElementById(canvasId);
    if (!ctx) return null;

    return new Chart(ctx, {
        type: 'bar',
        data: {
            labels: timeSlots,
            datasets: doctors.map(function(doc, i) {
                return {
                    label: doc,
                    data: appointments[i] || [],
                    backgroundColor: ['#3b82f6', '#22c55e', '#f59e0b'][i % 3] + '80',
                };
            }),
        },
        options: {
            responsive: true,
            indexAxis: 'y',
            scales: {
                x: { beginAtZero: true, title: { display: true, text: 'Appointments' } },
            },
        },
    });
}

// -- Confirmation dialog --------------------------------------------------
function confirmAction(message) {
    return window.confirm(message);
}
