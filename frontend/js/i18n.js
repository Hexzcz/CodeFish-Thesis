/**
 * English and Filipino, for the resident's view.
 *
 * The people this app is for speak Filipino. Every sentence they read was
 * written in plain language and then, until now, only in a second language.
 *
 * The console stays English on purpose — it is for researchers, its labels are
 * technical, and translating "TOPSIS closeness coefficient" helps nobody.
 *
 * Two ways a string gets here: `data-i18n` on an element in the markup, and
 * `t(key, params)` for anything built at runtime. Keys read as English so a
 * missing translation degrades to something legible rather than to a key.
 */

const LANGUAGE_KEY = 'codefish.language';
const LANGUAGES = ['en', 'fil'];

const STRINGS = {
    en: {
        tagline: 'Flood-aware evacuation routing · Quezon City District 1',

        // Asking
        where_are_you: 'Where are you right now?',
        use_my_location: 'Use my location',
        or_tap_the_map: 'Or tap the map',
        tap_hint: 'Tap where you are on the map →',
        finding_you: 'Finding where you are…',
        looking_for_route: 'Looking for the safest way out…',

        // Answering
        go_here: 'GO HERE',
        walk_time_minutes: 'about {minutes} min walk',
        walk_time_hours: 'about {hours} hr walk',
        walk_time_hours_minutes: 'about {hours} hr {minutes} min walk',
        nearest_center: 'Nearest evacuation center',
        one_more_center_here: '1 more evacuation center is at the same place',
        more_centers_here: '{count} more evacuation centers are at the same place',

        // What the flood model means, in words
        route_avoids_flooding: 'This route avoids flood-prone roads',
        roads_may_flood: '{risky} of {total} roads on this route may flood',
        parts_may_flood: 'Parts of this route may flood',
        still_safest: 'It is still the safest way out from where you are.',
        route_crosses_flooding: 'This route crosses flood-prone roads',
        take_care_or_wait: 'Take care, or wait where you are if you can.',
        shorter_ways_flood: 'Shorter ways exist, but they cross roads that may flood.',
        all_roads_clear: 'all roads clear',
        one_road_may_flood: '1 road may flood',
        n_roads_may_flood: '{count} roads may flood',

        // Getting there
        show_me_the_way: 'Show me the way',
        hide_the_way: 'Hide the way',
        walk_along_these: 'Walk along these roads',
        follow_route_on_map: 'Follow the highlighted route on the map.',
        unnamed_road: 'Unnamed road',
        other_option: 'Other option (1)',
        other_options: 'Other options ({count})',
        start_over: 'Start over',

        // Navigating
        start_navigation: 'Start navigation',
        stop_navigation: 'Stop navigation',
        walking_to: 'WALKING TO',
        recenter_on_me: 'Recenter on me',
        following_you: 'Following your location',
        following_offline: 'Following your location — offline',
        off_route: 'You are off the recommended route',
        updating_route: 'Updating your route…',
        route_updated: 'Safer route updated',
        rain_heavier_checking: 'Heavier rain — checking your route again',
        rain_eased_checking: 'The rain has eased — checking your route again',
        route_updated_heavier: 'Route updated for the heavier rain',
        route_updated_eased: 'Route updated — the rain has eased',
        arrived: 'You have arrived',
        stay_safe: 'Stay safe',
        accuracy_poor: 'Location accurate to about {metres} m',
        distance_needs_connection: 'Distance left and route checks need a connection',

        // When something is wrong
        offline_banner: 'You are offline — a new route needs a connection.',
        offline_no_new_route: 'You are offline. A new route needs a connection.',
        no_route_from_there: 'Could not find a route from there.',
        location_refused: 'Location permission was refused. Turn it on in your browser settings to follow your position.',
        location_unavailable: 'Your location is unavailable right now — GPS may be blocked indoors.',
        location_slow: 'Finding your location is taking too long. Move somewhere with a clearer view of the sky.',
        location_failed: 'Your location could not be found.',
        location_not_supported: 'This browser cannot follow your location. You can still read the directions.',
        location_needs_https: 'Live location needs a secure (https) connection. You can still read the directions.',
        could_not_get_location: 'Could not get your location. Tap the map to show where you are.',
        reroute_failed: 'Could not update your route — keep following the one shown',
        reroute_offline: 'Your route cannot be updated without a connection. The route shown is the last safe one worked out for you.',
        offline_and_off_route: 'You are off the route, and offline',
        advanced_view: 'Advanced view',
    },

    // Filipino as it is actually spoken in Metro Manila: everyday words, and
    // the English kept where English is what people say — "evacuation center",
    // "GPS", "route" is translated as "ruta" because that one is common.
    fil: {
        tagline: 'Paghahanap ng ligtas na daan palabas · Distrito 1, Lungsod Quezon',

        where_are_you: 'Nasaan ka ngayon?',
        use_my_location: 'Gamitin ang lokasyon ko',
        or_tap_the_map: 'O i-tap ang mapa',
        tap_hint: 'I-tap sa mapa kung nasaan ka →',
        finding_you: 'Hinahanap kung nasaan ka…',
        looking_for_route: 'Hinahanap ang pinakaligtas na daan palabas…',

        go_here: 'PUNTA DITO',
        walk_time_minutes: 'mga {minutes} minutong lakad',
        walk_time_hours: 'mga {hours} oras na lakad',
        walk_time_hours_minutes: 'mga {hours} oras {minutes} minutong lakad',
        nearest_center: 'Pinakamalapit na evacuation center',
        one_more_center_here: 'May 1 pang evacuation center sa lugar na ito',
        more_centers_here: 'May {count} pang evacuation center sa lugar na ito',

        route_avoids_flooding: 'Hindi dumadaan ang rutang ito sa mga kalsadang madalas bahain',
        roads_may_flood: '{risky} sa {total} kalsada sa rutang ito ang maaaring bahain',
        parts_may_flood: 'May bahagi ng rutang ito na maaaring bahain',
        still_safest: 'Ito pa rin ang pinakaligtas na daan mula sa kinaroroonan mo.',
        route_crosses_flooding: 'Dumadaan ang rutang ito sa mga kalsadang madalas bahain',
        take_care_or_wait: 'Mag-ingat, o manatili muna kung kaya mo.',
        shorter_ways_flood: 'May mas maikling daan, pero dumadaan ito sa mga kalsadang maaaring bahain.',
        all_roads_clear: 'malinis ang lahat ng kalsada',
        one_road_may_flood: '1 kalsada ang maaaring bahain',
        n_roads_may_flood: '{count} kalsada ang maaaring bahain',

        show_me_the_way: 'Ipakita ang daan',
        hide_the_way: 'Itago ang daan',
        walk_along_these: 'Dumaan sa mga kalsadang ito',
        follow_route_on_map: 'Sundan ang naka-highlight na ruta sa mapa.',
        unnamed_road: 'Kalsadang walang pangalan',
        other_option: 'Isa pang pagpipilian (1)',
        other_options: '{count} pang pagpipilian',
        start_over: 'Magsimula muli',

        start_navigation: 'Simulan ang paglalakad',
        stop_navigation: 'Itigil ang paglalakad',
        walking_to: 'PAPUNTA SA',
        recenter_on_me: 'Ibalik sa akin',
        following_you: 'Sinusundan ang lokasyon mo',
        following_offline: 'Sinusundan ang lokasyon mo — offline',
        off_route: 'Wala ka sa inirerekomendang ruta',
        updating_route: 'Ina-update ang ruta mo…',
        route_updated: 'Na-update ang mas ligtas na ruta',
        rain_heavier_checking: 'Lumakas ang ulan — sinusuri ulit ang ruta mo',
        rain_eased_checking: 'Humina ang ulan — sinusuri ulit ang ruta mo',
        route_updated_heavier: 'Na-update ang ruta dahil sa mas malakas na ulan',
        route_updated_eased: 'Na-update ang ruta — humina na ang ulan',
        arrived: 'Nakarating ka na',
        stay_safe: 'Mag-ingat ka',
        accuracy_poor: 'Tumpak ang lokasyon sa mga {metres} m',
        distance_needs_connection: 'Kailangan ng koneksyon para sa natitirang distansya at pagsusuri ng ruta',

        offline_banner: 'Offline ka — kailangan ng koneksyon para sa bagong ruta.',
        offline_no_new_route: 'Offline ka. Kailangan ng koneksyon para sa bagong ruta.',
        no_route_from_there: 'Walang mahanap na ruta mula diyan.',
        location_refused: 'Hindi pinayagan ang lokasyon. I-on ito sa settings ng browser mo para masundan ang kinaroroonan mo.',
        location_unavailable: 'Hindi makuha ang lokasyon mo ngayon — maaaring humihina ang GPS sa loob ng gusali.',
        location_slow: 'Matagal makuha ang lokasyon mo. Lumipat sa lugar na mas bukas ang langit.',
        location_failed: 'Hindi mahanap ang lokasyon mo.',
        location_not_supported: 'Hindi masusundan ng browser na ito ang lokasyon mo. Mababasa mo pa rin ang direksyon.',
        location_needs_https: 'Kailangan ng secure (https) na koneksyon para sa live na lokasyon. Mababasa mo pa rin ang direksyon.',
        could_not_get_location: 'Hindi makuha ang lokasyon mo. I-tap ang mapa kung nasaan ka.',
        reroute_failed: 'Hindi na-update ang ruta — sundan pa rin ang nakikita mong ruta',
        reroute_offline: 'Hindi ma-update ang ruta mo nang walang koneksyon. Ang nakikita mo ay ang huling ligtas na ruta para sa iyo.',
        offline_and_off_route: 'Wala ka sa ruta, at offline ka',
        advanced_view: 'Advanced view',
    },
};

/** The chosen language: a saved choice, then the browser's, then English. */
function resolveLanguage() {
    try {
        const saved = localStorage.getItem(LANGUAGE_KEY);
        if (LANGUAGES.includes(saved)) return saved;
    } catch (e) {
        // Private browsing. Fall through to the browser's own setting.
    }

    // Filipino, Tagalog, and the codes phones in the Philippines actually send.
    const preferred = (navigator.languages || [navigator.language || 'en']).join(',').toLowerCase();
    return /\b(fil|tl)\b|-ph\b/.test(preferred) ? 'fil' : 'en';
}

function currentLanguage() {
    return document.documentElement.lang === 'fil' ? 'fil' : 'en';
}

/** Look up a string, filling in {placeholders}. */
function t(key, params = {}) {
    const table = STRINGS[currentLanguage()] || STRINGS.en;
    const template = table[key] !== undefined ? table[key] : STRINGS.en[key];

    if (template === undefined) {
        console.warn('[i18n] no string for', key);
        return key;
    }
    return template.replace(/\{(\w+)\}/g, (whole, name) =>
        params[name] !== undefined ? params[name] : whole);
}

function setLanguage(language) {
    if (!LANGUAGES.includes(language)) return;
    try {
        localStorage.setItem(LANGUAGE_KEY, language);
    } catch (e) {
        // Not saved, but the page below still switches.
    }
    document.documentElement.lang = language;
    applyStaticTranslations();
    document.dispatchEvent(new CustomEvent('codefish:language-changed', { detail: { language } }));
}

/** Translate everything in the markup carrying a data-i18n key. */
function applyStaticTranslations() {
    document.querySelectorAll('[data-i18n]').forEach(element => {
        element.textContent = t(element.dataset.i18n);
    });
    document.querySelectorAll('[data-i18n-label]').forEach(element => {
        element.setAttribute('aria-label', t(element.dataset.i18nLabel));
    });

    const toggle = document.getElementById('language-toggle');
    if (toggle) {
        toggle.querySelectorAll('button').forEach(button => {
            button.classList.toggle('active', button.dataset.language === currentLanguage());
        });
    }
}

document.documentElement.lang = resolveLanguage();
document.addEventListener('DOMContentLoaded', applyStaticTranslations);
