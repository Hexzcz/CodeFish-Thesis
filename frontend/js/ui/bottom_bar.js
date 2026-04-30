function buildRouteTab(route, index) {
    const colorVar = `var(--route-${index + 1})`;
    const props = route.properties || {};
    const badge = props.recommended ? 'RECOMMENDED' : 'ALTERNATIVE';
    const dist = (props.total_length_km || 0).toFixed(2);
    const risk = getRiskLabel(props.flood_exposure || 0);
    const safe = Math.round(props.safety_score || 0);

    return `
    <div class="route-tab ${index === 0 ? 'active' : ''}"
         data-route="${index}"
         style="--tab-color:${colorVar}"
         onclick="selectRouteTab(${index})">
        <div class="tab-top">
            <span class="tab-rank">R${index + 1}</span>
            <span class="tab-badge">${badge}</span>
        </div>
        <div class="tab-bottom">
            <span>${dist} km</span>
            <span class="tab-dot">·</span>
            <span>${risk}</span>
            <span class="tab-dot">·</span>
            <span>${safe}%</span>
        </div>
    </div>`;
}

function selectRouteTab(index) {
    selectRoute(index);
}

function showBottomBar(routes) {
    const bar = document.getElementById('bottom-bar');
    const tabs = document.getElementById('route-tabs');
    tabs.innerHTML = routes.map((r, i) => buildRouteTab(r, i)).join('');
    bar.style.display = 'flex';

    // Give map room at bottom
    document.getElementById('map-container').style.paddingBottom = 'var(--bottom-bar)';
}

function hideBottomBar() {
    document.getElementById('bottom-bar').style.display = 'none';
    document.getElementById('map-container').style.paddingBottom = '0';
}
