/**
 * Shared plumbing for the browser tests.
 *
 * MapLibre needs WebGL, which a headless browser only has through a software
 * renderer — hence the swiftshader flags. Without them the 3D tests fail for
 * reasons that have nothing to do with CodeFish.
 */
const puppeteer = require('puppeteer');

const BASE_URL = process.env.CODEFISH_URL || 'http://127.0.0.1:8000';

// Somewhere on the District 1 road network, used as the origin everywhere.
const ORIGIN = { lat: 14.6357, lon: 121.0219 };

async function launch() {
  return puppeteer.launch({
    headless: 'new',
    args: [
      '--enable-unsafe-swiftshader',
      '--use-gl=swiftshader',
      '--no-sandbox',
      '--disable-dev-shm-usage',
    ],
  });
}

async function openResidentView(browser, { width = 420, height = 860 } = {}) {
  const page = await browser.newPage();
  await page.setViewport({ width, height, deviceScaleFactor: 2 });
  await page.goto(`${BASE_URL}/?mode=simple`, { waitUntil: 'networkidle2', timeout: 60000 });
  return page;
}

/** Drop the origin pin and wait for the route to come back. */
async function routeFrom(page, origin = ORIGIN) {
  await page.evaluate((o) => {
    simpleTapTheMap();
    window.appState.map.fire('click', { latlng: L.latLng(o.lat, o.lon) });
  }, origin);

  await page.waitForFunction(
    () => ((window.appState.routeData || {}).routes || []).length > 0,
    { timeout: 45000, polling: 250 }
  );

  return page.evaluate(() => {
    const routes = window.appState.routeData.routes;
    const best = routes.find(r => r.properties.recommended) || routes[0];
    return {
      count: routes.length,
      km: best.properties.total_length_km,
      name: best.properties.destination_name,
      coordinates: (best.geometry.coordinates || []).flat(),
    };
  });
}

const text = (page, id) =>
  page.evaluate(sel => (document.getElementById(sel) || {}).textContent || '', id);

/** Wait until an element's text satisfies a predicate, or fail loudly. */
async function waitForText(page, id, predicate, { timeout = 30000, label = '' } = {}) {
  const started = Date.now();
  let last = '';
  while (Date.now() - started < timeout) {
    last = await text(page, id);
    if (predicate(last)) return last;
    await new Promise(r => setTimeout(r, 300));
  }
  throw new Error(`timed out waiting for #${id} ${label} — last value: ${JSON.stringify(last)}`);
}

const sleep = ms => new Promise(r => setTimeout(r, ms));

module.exports = { BASE_URL, ORIGIN, launch, openResidentView, routeFrom, text, waitForText, sleep };
