/**
 * The app is usable by someone who cannot see it, or cannot use a mouse.
 *
 * This is an emergency tool for the public, so this is not a nice-to-have.
 * axe catches the machine-detectable part — roughly a third of what matters —
 * so the checks after it cover the things it structurally cannot see: whether
 * a keyboard can reach a control, and whether a change of state is announced.
 */
const { test, before, after, describe } = require('node:test');
const assert = require('node:assert');
const { AxePuppeteer } = require('@axe-core/puppeteer');
const { BASE_URL, launch, openResidentView, routeFrom } = require('./helpers');

const WCAG = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'];

async function seriousViolations(page) {
    const results = await new AxePuppeteer(page).withTags(WCAG).analyze();
    return results.violations
        .filter(v => v.impact === 'serious' || v.impact === 'critical')
        .map(v => `${v.id} (${v.impact}): ${v.help} — ${v.nodes.length} element(s)`);
}

describe('accessibility', () => {
    let browser, page;

    before(async () => {
        browser = await launch();
        page = await openResidentView(browser);
    });

    after(async () => { if (browser) await browser.close(); });

    test('the resident view has no serious WCAG violations', async () => {
        assert.deepEqual(await seriousViolations(page), []);
    });

    test('...and still none once a route is showing', async () => {
        // Route markers were the regression here: Leaflet marks them as
        // buttons, and until they were named a screen reader announced a
        // screenful of anonymous ones.
        await routeFrom(page);
        assert.deepEqual(await seriousViolations(page), []);
    });

    test('the address field has a real label, not just a placeholder', async () => {
        const named = await page.evaluate(() => {
            const input = document.getElementById('origin-search-input');
            const label = document.querySelector('label[for="origin-search-input"]');
            return Boolean(label && label.textContent.trim()) || Boolean(input.getAttribute('aria-label'));
        });
        assert.equal(named, true, 'the address input is labelled only by its placeholder');
    });

    test('what the app says about your route is announced, not just drawn', async () => {
        const announced = await page.evaluate(() => {
            const live = el => el && (el.getAttribute('role') === 'status' || el.getAttribute('role') === 'alert'
                || el.getAttribute('aria-live'));
            return {
                verdict: !!live(document.getElementById('simple-verdict')),
                error: !!live(document.getElementById('simple-error')),
                navStatus: !!live(document.getElementById('nav-status')),
            };
        });
        assert.deepEqual(announced, { verdict: true, error: true, navStatus: true });
    });

    test('the console keeps its per-road flood colouring', async () => {
        // The single colour is for residents. The console is where the
        // segment breakdown is the evidence, so it must not follow.
        await page.setViewport({ width: 1280, height: 900, deviceScaleFactor: 1 });
        await page.goto(`${BASE_URL}/?mode=admin`, { waitUntil: 'networkidle2' });
        await page.evaluate(() => {
            window.appState.placingOrigin = true;
            window.appState.map.fire('click', { latlng: L.latLng(14.6300, 121.0100) });
        });
        await page.evaluate(() => findRoutes());
        await page.waitForFunction(() => (window._segmentPolylines || []).length > 0,
            { timeout: 45000, polling: 250 });

        const colours = await page.evaluate(() =>
            [...new Set((window._segmentPolylines[0] || []).map(p => p.options.color))]);

        assert.ok(colours.length > 1,
            `the console lost its per-road colouring: ${colours.join(', ')}`);
    });

    test('every switch in the console can be reached and read by a keyboard', async () => {
        // The console is a desktop view: on a phone-width viewport it shows a
        // notice over everything pointing to the resident's view instead, and
        // that notice would swallow every click here.
        await page.setViewport({ width: 1280, height: 900, deviceScaleFactor: 1 });
        await page.goto(`${BASE_URL}/?mode=admin`, { waitUntil: 'networkidle2' });
        await page.waitForSelector('.toggle-switch');

        const broken = await page.evaluate(() =>
            [...document.querySelectorAll('.toggle-switch')]
                .filter(t => t.getAttribute('role') !== 'switch'
                    || t.getAttribute('tabindex') === null
                    || t.getAttribute('aria-checked') === null
                    || !t.getAttribute('aria-label'))
                .map(t => t.id || t.dataset.layer || 'unnamed'));

        assert.deepEqual(broken, [], 'these switches are not keyboard accessible');
    });

    test('a switch responds to the keyboard, not only the mouse', async () => {
        // Only the open tab's panel is displayed, and an element inside a
        // hidden one cannot take focus — so open Layers before reaching for a
        // switch, the same way a person would.
        await page.click('#left-tab-bar .tab[data-panel="layers"]');
        await page.waitForFunction(() => {
            const toggle = document.querySelector('#clip-toggle');
            return toggle && toggle.offsetParent !== null;
        });

        const before = await page.evaluate(() => {
            const toggle = document.querySelector('#clip-toggle');
            toggle.focus();
            return { checked: toggle.getAttribute('aria-checked'), focused: document.activeElement === toggle };
        });
        assert.equal(before.focused, true, 'the switch could not take keyboard focus');

        await page.keyboard.press('Enter');
        // aria-checked is mirrored from the class by a MutationObserver, whose
        // callback runs after the current task — read it on the next frame.
        await new Promise(r => setTimeout(r, 150));

        const after = await page.evaluate(() =>
            document.querySelector('#clip-toggle').getAttribute('aria-checked'));
        assert.notEqual(after, before.checked, 'Enter did not operate the switch');
    });

    test('keyboard focus is visible', async () => {
        // Tab, rather than element.focus(): :focus-visible is about how focus
        // arrived, and only a real keyboard press reproduces that.
        await page.evaluate(() => document.body.focus());
        await page.keyboard.press('Tab');

        const focus = await page.evaluate(() => {
            const active = document.activeElement;
            const style = getComputedStyle(active);
            return {
                tag: active.tagName,
                outlined: style.outlineStyle !== 'none' && parseFloat(style.outlineWidth) > 0,
            };
        });
        assert.equal(focus.outlined, true, `focus on <${focus.tag}> shows no visible outline`);
    });
});
