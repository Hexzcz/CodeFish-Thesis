/**
 * Making the controls usable without a mouse.
 *
 * The layer and centre toggles are styled <div>s with click handlers. They
 * look like switches and behave like switches for anyone using a pointer, but
 * a keyboard cannot reach them and a screen reader cannot tell what they are
 * or whether they are on.
 *
 * Rather than rewrite eight controls and their handlers, this upgrades them in
 * place: the role and the state that were missing, keyboard activation, and an
 * observer that keeps `aria-checked` honest when something else flips them.
 */

function upgradeToggles() {
    document.querySelectorAll('.toggle-switch').forEach(toggle => {
        if (toggle.dataset.a11yReady) return;
        toggle.dataset.a11yReady = 'true';

        toggle.setAttribute('role', 'switch');
        toggle.setAttribute('tabindex', '0');
        toggle.setAttribute('aria-checked', String(toggle.classList.contains('active')));

        if (!toggle.getAttribute('aria-label')) {
            toggle.setAttribute('aria-label', _labelFor(toggle));
        }

        // Space and Enter are what a switch responds to.
        toggle.addEventListener('keydown', (event) => {
            if (event.key !== ' ' && event.key !== 'Enter') return;
            event.preventDefault();
            toggle.click();
        });

        // The click handlers toggle a class; mirror that into the state a
        // screen reader reads, wherever the change comes from.
        new MutationObserver(() => {
            toggle.setAttribute('aria-checked', String(toggle.classList.contains('active')));
        }).observe(toggle, { attributes: true, attributeFilter: ['class'] });
    });
}

/** Borrow the visible text beside the switch, so the two never disagree. */
function _labelFor(toggle) {
    const row = toggle.closest('.layer-row, .toggle-row');
    const name = row && row.querySelector('.layer-name, .toggle-label');
    return name ? name.textContent.trim() : 'Toggle';
}

document.addEventListener('DOMContentLoaded', upgradeToggles);
