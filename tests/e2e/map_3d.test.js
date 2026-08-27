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

  test('the basemap is a real map, not a demand for an API key', async () => {
    // This exists because a provider was swapped in that answered 200 with a
    // picture reading "API KEY REQUIRED" straight across the map. The tiles
    // loaded, every test passed, and the app looked broken on a phone. A
    // watermark or a "no data" placeholder is nearly flat; a real map is not.
    // Derive the tile from the district itself rather than hardcoding numbers
    // that quietly point at open ocean.
    const tileUrl = await page.evaluate(() => {
      const [lon, lat] = [121.02, 14.645];
      const z = 17;
      const n = 2 ** z;
      const x = Math.floor((lon + 180) / 360 * n);
      const y = Math.floor((1 - Math.asinh(Math.tan(lat * Math.PI / 180)) / Math.PI) / 2 * n);
      return get3DMap().getStyle().sources.basemap.tiles[0]
        .replace('{z}', String(z)).replace('{x}', String(x)).replace('{y}', String(y));
    });

    const tile = await page.evaluate(async (url) => {
      const bitmap = await createImageBitmap(await (await fetch(url)).blob());
      const canvas = new OffscreenCanvas(bitmap.width, bitmap.height);
      const context = canvas.getContext('2d');
      context.drawImage(bitmap, 0, 0);
      const { data } = context.getImageData(0, 0, bitmap.width, bitmap.height);

      const counts = new Map();
      for (let i = 0; i < data.length; i += 4) {
        const colour = (data[i] << 16) | (data[i + 1] << 8) | data[i + 2];
        counts.set(colour, (counts.get(colour) || 0) + 1);
      }
      const pixels = data.length / 4;
      return {
        colours: counts.size,
        dominantShare: Math.max(...counts.values()) / pixels,
      };
    }, tileUrl);

    // Two checks, because the two ways this fails look different. Measured
    // over District 1 at zoom 17:
    //
    //   Carto without a key   15 colours,  45% one colour  ← watermark
    //   Esri dark canvas     123 colours,  94% one colour  ← "no data" tile
    //   OpenStreetMap        256 colours,  37% one colour  ← a real map
    //   Esri imagery      42,808 colours, 0.1% one colour  ← a real map
    assert.ok(
      tile.colours > 40,
      `the basemap tile has only ${tile.colours} distinct colours — that is a ` +
      'watermark or an error image, not a map'
    );
    assert.ok(
      tile.dominantShare < 0.8,
      `${Math.round(tile.dominantShare * 100)}% of the basemap tile is a single ` +
      'colour — the provider has no tiles at this zoom'
    );
  });


  test('terrain tiles come from CodeFish, not a third party', async () => {
    // The DEM is the project's own; a 3D view that depended on someone else's
    // elevation service would stop working offline.
    const terrainUrl = await page.evaluate(() => get3DMap().getStyle().sources.terrain.tiles[0]);
    assert.ok(terrainUrl.includes('/tiles/terrain-rgb/'), `unexpected terrain source: ${terrainUrl}`);
  });
});
