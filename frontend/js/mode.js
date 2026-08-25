/**
 * Which face of the app you get: `simple` for a resident, `admin` for the
 * console with every control and number.
 *
 * Simple is the default because most people opening this are trying to find
 * out where to go, not to inspect a model. Admin is reached with ?mode=admin
 * and then remembered, so a researcher sets it once per browser.
 *
 * The mode is written to <html data-mode>, and CSS does the rest — both views
 * share one page and one map rather than two copies of the app.
 */

const MODES = ['simple', 'admin'];
const MODE_STORAGE_KEY = 'codefish.mode';

/** Resolve the mode: URL wins, then what this browser remembered, then simple. */
function resolveMode() {
    const requested = new URLSearchParams(window.location.search).get('mode');
    if (MODES.includes(requested)) {
        try {
            localStorage.setItem(MODE_STORAGE_KEY, requested);
        } catch (e) {
            // Private browsing: the URL still worked, it just will not persist.
        }
        return requested;
    }

    let remembered = null;
    try {
        remembered = localStorage.getItem(MODE_STORAGE_KEY);
    } catch (e) {
        remembered = null;
    }
    return MODES.includes(remembered) ? remembered : 'simple';
}

function currentMode() {
    return document.documentElement.dataset.mode || 'simple';
}

function isAdminMode() {
    return currentMode() === 'admin';
}

/** Switch modes and reload, so every view rebuilds from a known state. */
function setMode(mode) {
    if (!MODES.includes(mode)) return;
    try {
        localStorage.setItem(MODE_STORAGE_KEY, mode);
    } catch (e) {
        // Fall through: the query string below still carries the choice.
    }
    window.location.search = `?mode=${mode}`;
}

// Applied inline in <head> too, before first paint — see index.html. Repeating
// it here keeps this file the single definition of what the modes are.
document.documentElement.dataset.mode = resolveMode();
