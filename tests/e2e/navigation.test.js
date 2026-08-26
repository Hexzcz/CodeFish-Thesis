/**
 * Walking a route with live location.
 *
 * The browser's geolocation is emulated, so this exercises the real
 * watchPosition path, the real permission grant and the real progress calls to
 * the backend — everything except an actual GPS chip.
 */
const { test, before, after, describe } = require('node:test');
const assert = require('node:assert');
const { BASE_URL, launch, openResidentView, routeFrom, text, waitForText, sleep } = require('./helpers');

const metres = value => Number(String(value).replace(/[^\d.]/g, '')) * (/km/.test(value) ? 1000 : 1);

describe('live navigation', () => {
  let browser, page, route, routeRequests;

  before(async () => {
    browser = await launch();
    await browser.defaultBrowserContext().overridePermissions(BASE_URL, ['geolocation']);
    page = await openResidentView(browser);

    routeRequests = [];
    page.on('request', r => {
      if (r.method() === 'POST' && r.url().endsWith('/route')) routeRequests.push(r.url());
    });

    route = await routeFrom(page);
    await page.evaluate(() => startNavigation());
    await waitForText(page, 'nav-destination', t => t.length > 0, { label: 'destination' });
  });

  after(async () => { if (browser) await browser.close(); });

  test('navigation names the destination and the distance left', async () => {
    assert.ok((await text(page, 'nav-destination')).length > 0);
    assert.ok(metres(await text(page, 'nav-remaining')) > 0);
  });

  test('distance falls as the walker advances along the route', async () => {
    const readings = [];
    for (const fraction of [0, 0.3, 0.6, 0.8]) {
      const point = route.coordinates[Math.floor(fraction * (route.coordinates.length - 1))];
      await page.setGeolocation({ latitude: point[1], longitude: point[0], accuracy: 8 });
      await sleep(3200);
      readings.push(metres(await text(page, 'nav-remaining')));
    }

    assert.ok(
      readings[readings.length - 1] < readings[0],
      `distance did not fall while walking the route: ${readings.join(' → ')}`
    );
    assert.match(await text(page, 'nav-status'), /following your location/i);
  });

  test('straying is noticed, and the new route comes from the flood-aware router', async () => {
    const before = routeRequests.length;
    const middle = route.coordinates[Math.floor(route.coordinates.length / 2)];

    // Far enough off to be unambiguous, and repeated: one stray fix is noise,
    // three in a row is a wrong turn.
    for (let i = 0; i < 4; i++) {
      await page.setGeolocation({
        latitude: middle[1] - 0.0013 - i * 0.0003,
        longitude: middle[0] - 0.0013,
        accuracy: 8,
      });
      await sleep(3200);
    }

    const status = await text(page, 'nav-status');
    assert.match(status, /off the recommended route|safer route updated|following/i);
    assert.ok(
      routeRequests.length > before,
      'straying did not produce a new route request'
    );
  });

  test('stopping clears the watcher and the panel', async () => {
    await page.evaluate(() => stopNavigation());
    const state = await page.evaluate(() => ({
      panelHidden: document.getElementById('nav-panel').classList.contains('hidden'),
      navigating: isNavigating(),
    }));
    assert.equal(state.panelHidden, true, 'the navigation panel is still showing');
    assert.equal(state.navigating, false, 'navigation is still running');
  });
});
