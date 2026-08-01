/**
 * BlockLaunch WebUI — Main JavaScript utilities
 */

// ── Toast Notifications ──────────────────────────────────────────────

function showToast(message, type = 'info', duration = 4000) {
    const container = document.getElementById('toast-container');
    if (!container) return;

    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.textContent = message;

    container.appendChild(toast);

    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateX(100%)';
        toast.style.transition = 'all 0.3s ease';
        setTimeout(() => toast.remove(), 300);
    }, duration);
}

// ── API Helper ───────────────────────────────────────────────────────

async function apiCall(url, method = 'GET', body = null) {
    const options = {
        method,
        headers: { 'Content-Type': 'application/json' },
    };
    if (body) {
        options.body = JSON.stringify(body);
    }
    const resp = await fetch(url, options);
    return resp.json();
}

// ── Auto-refresh server status ──────────────────────────────────────

function initStatusRefresh() {
    // If on a server detail page, periodically refresh status
    const statusDot = document.querySelector('.status-dot');
    if (statusDot) {
        setInterval(async () => {
            const serverName = window.location.pathname.split('/server/')[1];
            if (serverName) {
                try {
                    const status = await apiCall(`/api/servers/${serverName}`);
                    const dot = document.querySelector('.status-dot');
                    if (dot) {
                        dot.className = `status-dot ${status.status}`;
                    }
                } catch (e) {
                    // Ignore errors
                }
            }
        }, 5000);
    }
}

// ── Console auto-scroll ─────────────────────────────────────────────

function initConsoleAutoScroll() {
    const consoleOutput = document.getElementById('console-output');
    if (consoleOutput) {
        const observer = new MutationObserver(() => {
            consoleOutput.scrollTop = consoleOutput.scrollHeight;
        });
        observer.observe(consoleOutput, { childList: true });
    }
}

// ── Initialize on page load ─────────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {
    initStatusRefresh();
    initConsoleAutoScroll();
});
