const API_BASE = window.location.origin;

const ROUTE_COLORS_CSS = ['--route-1', '--route-2', '--route-3'];
const ROUTE_COLORS_HEX = ['#29b6f6', '#ce93d8', '#f06292'];

const SCENARIOS = ['5yr', '25yr', '100yr'];
const K_ROUTES = 3;

function getRiskColor(flood_proba) {
    if (flood_proba < 0.10) return 'var(--safe)';
    if (flood_proba < 0.25) return 'var(--low)';
    if (flood_proba < 0.45) return 'var(--moderate)';
    if (flood_proba < 0.65) return 'var(--high)';
    return 'var(--critical)';
}

function getRiskColorHex(flood_proba) {
    if (flood_proba < 0.10) return '#4caf7d';
    if (flood_proba < 0.25) return '#8bc34a';
    if (flood_proba < 0.45) return '#ffc107';
    if (flood_proba < 0.65) return '#ff7043';
    return '#e53935';
}

function getRiskLabel(flood_proba) {
    if (flood_proba < 0.10) return 'Safe';
    if (flood_proba < 0.25) return 'Low';
    if (flood_proba < 0.45) return 'Moderate';
    if (flood_proba < 0.65) return 'High';
    return 'Critical';
}
