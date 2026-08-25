/**
 * Turning model output into sentences.
 *
 * The engine deals in flood probabilities and TOPSIS closeness. A person
 * deciding whether to walk somewhere needs neither. Everything the simple view
 * says about a route is decided here, in one place, so the wording cannot
 * drift between the card, the banner and the alternatives list.
 */

// A brisk walk on flat ground. Deliberately not adjusted for flooding: the
// number is a rough expectation, and pretending to model wading is worse.
const WALKING_METRES_PER_MINUTE = 80;

// Flood exposure above this and the route gets a warning banner rather than a
// reassurance. Matches the 'High' band the engine assigns in topsis.py.
const HIGH_RISK_EXPOSURE = 0.40;
const SOME_RISK_EXPOSURE = 0.15;

function walkingTime(metres) {
    const minutes = Math.max(1, Math.round(metres / WALKING_METRES_PER_MINUTE));
    if (minutes < 60) return `about ${minutes} min walk`;
    const hours = Math.floor(minutes / 60);
    const rest = minutes % 60;
    return rest ? `about ${hours} hr ${rest} min walk` : `about ${hours} hr walk`;
}

function formatDistance(km) {
    const metres = (km || 0) * 1000;
    return metres < 1000 ? `${Math.round(metres)} m` : `${km.toFixed(1)} km`;
}

/** How many roads on this route the model expects to flood. */
function riskySegmentCount(props) {
    const counts = props.flood_class_counts || {};
    const low = counts['1'] || counts[1] || 0;
    const high = counts['2'] || counts[2] || 0;
    return low + high;
}

/** "all roads clear" / "1 road may flood" / "4 roads may flood" */
function riskPhrase(props) {
    const risky = riskySegmentCount(props);
    if (!risky) return 'all roads clear';
    return risky === 1 ? '1 road may flood' : `${risky} roads may flood`;
}

/** How this route reads to someone deciding whether to take it. */
function routeVerdict(props) {
    const exposure = props.flood_exposure || 0;
    const risky = riskySegmentCount(props);

    if (exposure >= HIGH_RISK_EXPOSURE) {
        return {
            level: 'high',
            headline: 'This route crosses flood-prone roads',
            detail: 'Take care, or wait where you are if you can.',
        };
    }
    if (exposure >= SOME_RISK_EXPOSURE || risky > 0) {
        return {
            level: 'some',
            headline: risky
                ? `${risky} of ${props.segment_count} roads on this route may flood`
                : 'Parts of this route may flood',
            detail: 'It is still the safest way out from where you are.',
        };
    }
    return {
        level: 'safe',
        headline: 'This route avoids flood-prone roads',
        detail: '',
    };
}

/**
 * Why the recommended route is not simply the shortest one.
 *
 * Left unsaid, a longer recommendation looks like a mistake — the shorter
 * option is right there in the list. Only claimed when it is true of every
 * shorter alternative, so the sentence never oversells the choice.
 */
function whyThisRoute(best, routes) {
    const bestRisky = riskySegmentCount(best.properties);
    const shorter = routes.filter(r =>
        r !== best && (r.properties.total_length_km || 0) < (best.properties.total_length_km || 0));

    if (!shorter.length) return '';
    const allShorterAreRiskier = shorter.every(r => riskySegmentCount(r.properties) > bestRisky);
    return allShorterAreRiskier
        ? 'Shorter ways exist, but they cross roads that may flood.'
        : '';
}

/**
 * The destination as a person would say it.
 *
 * The router labels clustered destinations "Barangay Hall (+2 nearby)" —
 * useful in the console, noise on a card that is trying to name one place to
 * walk to. The count moves to its own quiet line instead.
 */
function destinationName(props) {
    const raw = props.destination_name || 'Nearest evacuation center';
    return raw.replace(/\s*\(\+\d+\s*nearby\)\s*$/, '').trim();
}

/** "2 more centers at the same spot", or nothing when it is a single place. */
function destinationNote(props) {
    const match = /\(\+(\d+)\s*nearby\)/.exec(props.destination_name || '');
    if (!match) return '';
    const others = Number(match[1]);
    return others === 1
        ? '1 more evacuation center is at the same place'
        : `${others} more evacuation centers are at the same place`;
}

/** One line for an alternative route in the list. */
function routeSummaryLine(props) {
    return `${formatDistance(props.total_length_km)} · ${riskPhrase(props)}`;
}
