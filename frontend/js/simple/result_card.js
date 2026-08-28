/**
 * The answer: where to go, how far, and whether it is safe.
 *
 * One card, four facts, in the order someone needs them. Everything the admin
 * view shows about scoring — TOPSIS closeness, WSM cost, per-segment
 * probabilities — is deliberately absent; see docs/decisions/0005-two-views.md.
 */

function renderSimpleResult(routes) {
    const stale = document.getElementById('simple-stale');
    if (stale && navigator.onLine) stale.classList.add('hidden');

    const best = routes.find(r => r.properties.recommended) || routes[0];
    const props = best.properties;
    const verdict = routeVerdict(props);

    _renderDestination(props);
    _renderVerdict(verdict);
    _renderWhyThisRoute(whyThisRoute(best, routes));
    _renderAlternativesButton(routes);
    renderSimpleDirections(best);

    // Focus the map on the answer, not on the whole district.
    const bestIndex = routes.indexOf(best);
    selectRoute(bestIndex);
    fitToRoute(bestIndex);
}

function _renderDestination(props) {
    document.getElementById('simple-destination').textContent = destinationName(props);
    document.getElementById('simple-distance').textContent =
        `${formatDistance(props.total_length_km)} · ${walkingTime((props.total_length_km || 0) * 1000)}`;

    const note = document.getElementById('simple-dest-note');
    note.textContent = destinationNote(props);
    note.classList.toggle('hidden', !note.textContent);
}

function _renderVerdict(verdict) {
    const banner = document.getElementById('simple-verdict');
    banner.className = `simple-verdict simple-verdict-${verdict.level}`;
    banner.querySelector('.sv-headline').textContent = verdict.headline;

    const detail = banner.querySelector('.sv-detail');
    detail.textContent = verdict.detail;
    detail.classList.toggle('hidden', !verdict.detail);
}

function _renderWhyThisRoute(reason) {
    const el = document.getElementById('simple-why');
    el.textContent = reason;
    el.classList.toggle('hidden', !reason);
}

function _renderAlternativesButton(routes) {
    const btn = document.getElementById('simple-alternatives-btn');
    const others = routes.length - 1;
    btn.classList.toggle('hidden', others < 1);
    btn.textContent = others === 1 ? t('other_option') : t('other_options', { count: others });
}

/** The alternatives list, built only when someone asks to see it. */
function toggleSimpleAlternatives() {
    const panel = document.getElementById('simple-alternatives');
    const routes = (window.appState.routeData || {}).routes || [];
    if (routes.length < 2) return;

    const opening = panel.classList.contains('hidden');
    panel.classList.toggle('hidden', !opening);
    if (!opening) return;

    const best = routes.find(r => r.properties.recommended) || routes[0];
    panel.innerHTML = '';
    routes.forEach((route, index) => {
        if (route === best) return;
        const props = route.properties;
        const item = document.createElement('button');
        item.className = 'simple-alt';
        item.onclick = () => _chooseAlternative(index);
        item.innerHTML = `
            <span class="alt-name">${destinationName(props)}</span>
            <span class="alt-meta">${routeSummaryLine(props)}</span>`;
        panel.appendChild(item);
    });
}

function _chooseAlternative(index) {
    const routes = (window.appState.routeData || {}).routes || [];
    const chosen = routes[index];
    if (!chosen) return;

    const props = chosen.properties;
    _renderDestination(props);
    _renderVerdict(routeVerdict(props));
    _renderWhyThisRoute('');
    renderSimpleDirections(chosen);
    selectRoute(index);
    fitToRoute(index);
    document.getElementById('simple-alternatives').classList.add('hidden');
}
