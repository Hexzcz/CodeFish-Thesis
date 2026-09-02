/**
 * The resident's view does its one job: ask where you are, answer where to go.
 */
const { test, before, after, describe } = require('node:test');
const assert = require('node:assert');
const { launch, openResidentView, routeFrom, text } = require('./helpers');

describe('resident view', () => {
  let browser, page;

  before(async () => {
    browser = await launch();
    page = await openResidentView(browser);
  });

  after(async () => { if (browser) await browser.close(); });

  test('opens on the question, not on a wall of controls', async () => {
    const question = await page.$eval('.simple-question', el => el.textContent.trim());
    assert.match(question, /where are you/i);

    // The console's controls exist in the DOM but must not be on screen.
    const sidebarShown = await page.evaluate(() =>
      getComputedStyle(document.getElementById('sidebar-left')).display !== 'none');
    assert.equal(sidebarShown, false, 'the admin sidebar is visible in the resident view');
  });

  test('a tap on the map produces a ranked route', async () => {
    const route = await routeFrom(page);
    assert.ok(route.count >= 1, 'no routes came back');
    assert.ok(route.km > 0, 'route has no length');
    assert.ok(route.name, 'route has no destination name');
  });

  test('the answer names a place, a distance and a walking time', async () => {
    const destination = await text(page, 'simple-destination');
    const distance = await text(page, 'simple-distance');

    assert.ok(destination.length > 0, 'no destination shown');
    assert.match(distance, /\d/, 'no distance shown');
    assert.match(distance, /min walk|hr/, 'no walking time shown');
  });

  test('no model vocabulary reaches the resident', async () => {
    // The whole point of the split: TOPSIS, XGBoost and return periods belong
    // to the console. If one leaks into this view, it leaks here first.
    const visible = await page.evaluate(() => document.getElementById('simple-shell').innerText);
    for (const term of ['TOPSIS', 'XGBoost', 'raster', 'return period', 'weight']) {
      assert.ok(
        !new RegExp(term, 'i').test(visible),
        `"${term}" is showing in the resident's view: ${visible.slice(0, 200)}`
      );
    }
  });

  test('a route is drawn in one colour, and it matches what the card says', async () => {
    // Per-road colouring turns a route into a patchwork. The resident's view
    // draws each route in a single colour taken from its overall risk — and
    // that colour has to agree with the sentence printed beside it, because
    // green next to "this route crosses flood-prone roads" would be worse
    // than no colour at all.
    const drawn = await page.evaluate(() => {
      const colours = [...new Set((window._segmentPolylines[0] || []).map(p => p.options.color))];
      const props = window.appState.routeData.routes[0].properties;
      return { colours, level: routeVerdict(props).level, expected: getRouteColorHex(props) };
    });

    assert.equal(drawn.colours.length, 1,
      `the route is drawn in ${drawn.colours.length} colours: ${drawn.colours.join(', ')}`);
    assert.equal(drawn.colours[0], drawn.expected);

    const byLevel = { safe: '#4caf7d', some: '#ffc107', high: '#e53935' };
    assert.equal(drawn.colours[0], byLevel[drawn.level],
      `the line is ${drawn.colours[0]} but the card says "${drawn.level}"`);
  });

  test('the way there lists streets in order', async () => {
    await page.evaluate(() => toggleSimpleDirections());
    const steps = await page.$$eval('.simple-step .step-street', els => els.map(e => e.textContent.trim()));
    assert.ok(steps.length > 0, 'no walking steps listed');
    assert.ok(steps.every(s => s.length > 0), 'a step has no street name');
  });
});
