/**
 * The 3D view actually renders.
 *
 * This exists because of a specific bug: the style declared a text layer with
 * no `glyphs` font source, MapLibre rejected the whole style, and the map was
 * a black rectangle on every device. Nothing failed, no error surfaced, and it
 * took a phone and a server log to find. A test that asserts the style loads
 * would have caught it in seconds.
 */
const { test, before, after, describe } = require('node:test');
const assert = require('node:assert');
const { launch, openResidentView, routeFrom } = require('./helpers');

describe('3D navigation map', () => {
  let browser, page;

  before(async () => {
    browser = await launch();
    page = await openResidentView(browser);
  });

  after(async () => { if (browser) await browser.close(); });

  test('the style is valid and finishes loading', async () => {
    const result = await page.evaluate(async () => {
      const errors = [];
      await loadMapLibre();
      const map = new maplibregl.Map({
        container: document.getElementById('map-3d'),
        style: navigationStyle(),
        center: [121.02, 14.645],
        zoom: 15,
        pitch: 60,
      });
      map.on('error', e => errors.push((e.error && e.error.message) || 'unknown'));

      const loaded = await new Promise(resolve => {
        const timer = setTimeout(() => resolve(false), 20000);
        map.on('load', () => { clearTimeout(timer); resolve(true); });
      });
      return { loaded, errors };
    });

    assert.deepEqual(result.errors, [], `the map style reported errors: ${result.errors.join(' | ')}`);
    assert.equal(result.loaded, true, 'the 3D map never finished loading');
  });

  test('switching to 3D draws the route and its destination', async () => {
    await routeFrom(page);
    await page.evaluate(() => switchMapMode('3d'));

    await page.waitForFunction(
      () => { const m = get3DMap(); return m && m.isStyleLoaded(); },
      { timeout: 30000, polling: 500 }
    );

    const state = await page.evaluate(() => {
      const map = get3DMap();
      return {
        pitched: map.getPitch() > 30,
        terrain: !!map.getTerrain(),
        segments: map.getSource('route')._data.features.length,
        label: (document.querySelector('.nav-destination-marker') || {}).textContent || '',
      };
    });

    assert.ok(state.pitched, 'the 3D view is not tilted');
    assert.ok(state.terrain, 'terrain is not enabled');
    assert.ok(state.segments > 0, 'the route was not drawn in 3D');
    assert.ok(state.label.length > 0, 'the destination is not labelled');
  });

  test('terrain tiles come from CodeFish, not a third party', async () => {
    // The DEM is the project's own; a 3D view that depended on someone else's
    // elevation service would stop working offline.
    const terrainUrl = await page.evaluate(() => get3DMap().getStyle().sources.terrain.tiles[0]);
    assert.ok(terrainUrl.includes('/tiles/terrain-rgb/'), `unexpected terrain source: ${terrainUrl}`);
  });
});
