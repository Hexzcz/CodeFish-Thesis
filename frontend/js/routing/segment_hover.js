function showSegmentTooltip(e, props) {
    const tt = document.getElementById('seg-tooltip');
    const proba = props.flood_proba || 0;
    const color = getRiskColorHex(proba);

    document.getElementById('tt-name').textContent = props.name || 'Unnamed Road';
    document.getElementById('tt-type').textContent = props.highway || 'road';
    document.getElementById('tt-bar').style.width = (proba * 100) + '%';
    document.getElementById('tt-bar').style.background = color;
    document.getElementById('tt-prob').textContent = Math.round(proba * 100) + '%';
    document.getElementById('tt-class').textContent = 'Class ' + (props.flood_class || 0);

    tt.style.left = (e.originalEvent.pageX + 14) + 'px';
    tt.style.top = (e.originalEvent.pageY - 14) + 'px';
    tt.classList.remove('hidden');
}

function hideSegmentTooltip() {
    document.getElementById('seg-tooltip').classList.add('hidden');
}
