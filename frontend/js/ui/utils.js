// Shared utilities

function setStatus(label, computing = false) {
    const dot = document.getElementById('status-dot');
    const text = document.getElementById('status-text');
    if (dot) dot.className = 'status-dot' + (computing ? ' computing' : '');
    if (text) text.textContent = label;
}
