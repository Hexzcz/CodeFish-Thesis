document.addEventListener('DOMContentLoaded', async () => {
    console.log('CodeFish initializing…');

    // Init map
    initMap();

    // Init tab bars
    initTabs('#left-tab-bar', 'panel-');
    initTabs('#right-tab-bar', 'rpanel-');

    // Load data
    setStatus('LOADING', true);
    await Promise.all([fetchBoundary(), fetchRoads(), fetchCenters()]);
    setStatus('READY');

    // The admin console shows every center from the start. The simple view
    // waits until there is a route, so the first thing a resident sees is a
    // question rather than seventy pins.
    toggleEvacCenters(currentMode() === 'admin');

    console.log('CodeFish ready.');
});
