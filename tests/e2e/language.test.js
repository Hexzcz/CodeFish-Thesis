/**
 * The resident's view speaks Filipino.
 *
 * The people this app is for are Filipino speakers. This checks that choosing
 * the language actually changes what they read — including the sentences built
 * at runtime from the flood model, which are the ones most likely to be left
 * in English by accident.
 */
const { test, before, after, describe } = require('node:test');
const assert = require('node:assert');
const { launch, openResidentView, routeFrom } = require('./helpers');

describe('language', () => {
  let browser, page;

  before(async () => {
    browser = await launch();
    page = await openResidentView(browser);
  });

  after(async () => { if (browser) await browser.close(); });

  test('the question changes when Filipino is chosen', async () => {
    const english = await page.$eval('.simple-question', el => el.textContent.trim());
    await page.evaluate(() => setLanguage('fil'));
    const filipino = await page.$eval('.simple-question', el => el.textContent.trim());

    assert.notEqual(filipino, english);
    assert.match(filipino, /nasaan/i, 'the Filipino question does not look Filipino');
    assert.equal(await page.evaluate(() => document.documentElement.lang), 'fil');
  });

  test('the answer is Filipino too, not just the buttons', async () => {
    // These sentences are built at runtime from the flood model, so they are
    // the ones that get left behind when a translation pass misses something.
    await routeFrom(page);

    const answer = await page.evaluate(() => ({
      eyebrow: document.querySelector('.simple-eyebrow').textContent.trim(),
      distance: document.getElementById('simple-distance').textContent.trim(),
      verdict: document.querySelector('#simple-verdict .sv-headline').textContent.trim(),
    }));

    assert.match(answer.eyebrow, /punta/i);
    assert.match(answer.distance, /lakad/i, 'the walking time is still English');
    assert.match(answer.verdict, /rutang ito|kalsada/i, 'the flood verdict is still English');
  });

  test('switching back mid-result leaves nothing behind', async () => {
    await page.evaluate(() => setLanguage('en'));
    const verdict = await page.evaluate(() =>
      document.querySelector('#simple-verdict .sv-headline').textContent.trim());

    assert.match(verdict, /route/i, 'the verdict did not switch back to English');
  });

  test('the choice survives a reload', async () => {
    await page.evaluate(() => setLanguage('fil'));
    await page.reload({ waitUntil: 'networkidle2' });

    assert.equal(await page.evaluate(() => document.documentElement.lang), 'fil');
    assert.match(
      await page.$eval('.simple-question', el => el.textContent.trim()), /nasaan/i);
  });

  test('no key leaks onto the screen instead of a sentence', async () => {
    // t() returns the key itself when a string is missing; that must never
    // reach a person.
    const visible = await page.evaluate(() =>
      document.getElementById('simple-shell').innerText);

    assert.ok(!/\b[a-z]+_[a-z_]+\b/.test(visible),
      `an untranslated key is showing: ${visible.slice(0, 200)}`);
  });
});
