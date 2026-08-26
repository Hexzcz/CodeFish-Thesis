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

  test('the way there lists streets in order', async () => {
    await page.evaluate(() => toggleSimpleDirections());
    const steps = await page.$$eval('.simple-step .step-street', els => els.map(e => e.textContent.trim()));
    assert.ok(steps.length > 0, 'no walking steps listed');
    assert.ok(steps.every(s => s.length > 0), 'a step has no street name');
  });
});
