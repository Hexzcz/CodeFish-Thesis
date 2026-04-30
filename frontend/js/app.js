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

    // Default: centers visible
    toggleEvacCenters(true);

    console.log('CodeFish ready.');
});
