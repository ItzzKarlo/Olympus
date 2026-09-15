// Optional browser regression suite. Use a temporary Playwright installation;
// no browser automation dependency is shipped to the kiosk.
const { chromium } = require('playwright');
const assert = require('node:assert/strict');
(async () => {
  const browser = await chromium.launch({ executablePath: process.env.BROWSER_PATH || '/usr/bin/brave', headless: true });
  const page = await browser.newPage();
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  const base = process.env.PREVIEW_URL || 'http://127.0.0.1:5173/';
  const visit = async query => {
    await page.goto(`${base}?preview=idle&${query}`);
    await page.waitForSelector('.ambient-clock');
    await page.waitForTimeout(650);
  };
  for (const [width, height] of [[1920,1080], [2560,1440], [1366,768], [900,700], [390,844]]) {
    await page.setViewportSize({ width, height });
    let anchor;
    for (const panels of ['none','left','right','both']) {
      await visit(`panels=${panels}&seasonal_date=2026-11-11`);
      const box = await page.locator('.ambient-clock').boundingBox();
      assert(Math.abs(box.x + box.width / 2 - width / 2) < 1, `clock off center: ${width}/${panels}`);
      if (anchor) assert.equal(box.x, anchor.x);
      anchor = box;
      assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), `horizontal overflow: ${width}`);
    }
  }
  await page.setViewportSize({ width: 1920, height: 1080 });
  const events = { '2026-12-31':'new-years-eve', '2026-11-11':'st-martin', '2026-12-24':'christmas-eve', '2026-12-01':'advent', '2026-07-15':null, '2026-04-15':null, '2026-10-31':'halloween', '2026-04-05':'easter' };
  let realDate;
  for (const [date, event] of Object.entries(events)) {
    await visit(`seasonal_date=${date}`);
    assert.equal(await page.locator('.seasonal-environment').getAttribute('data-seasonal-event'), event);
    const displayed = await page.locator('.ambient-clock__date').innerText();
    if (realDate) assert.equal(displayed, realDate, 'seasonal override changed clock date');
    realDate = displayed;
    const contrast = await page.evaluate(() => {
      const style = getComputedStyle(document.querySelector('.olympus-display'));
      const luminance = value => {
        const probe = document.createElement('span'); probe.style.color = value;
        document.body.append(probe);
        const rgb = getComputedStyle(probe).color.match(/[\d.]+/g).slice(0, 3).map(Number);
        probe.remove();
        return rgb.map(n => { const c = n / 255; return c <= .04045 ? c / 12.92 : ((c + .055) / 1.055) ** 2.4; }).reduce((sum, c, i) => sum + c * [.2126,.7152,.0722][i], 0);
      };
      const foreground = luminance(style.getPropertyValue('--logo-primary'));
      const background = luminance(style.getPropertyValue('--background'));
      return (Math.max(foreground, background) + .05) / (Math.min(foreground, background) + .05);
    });
    assert(contrast >= 4.5, `logo contrast too low: ${date}: ${contrast}`);
    const count = await page.locator('.seasonal-environment *').count();
    assert(count < 300, `environment node budget exceeded: ${count}`);
    if (process.env.SCREENSHOT_DIR) await page.screenshot({path:`${process.env.SCREENSHOT_DIR}/${date}.png`});
  }
  await visit('alert=critical&panels=both');
  assert.equal(await page.locator('.seasonal-environment').getAttribute('data-intensity'), 'retreat');
  assert(await page.locator('[role="alert"]').isVisible());
  const layers = await page.evaluate(() => ['.event-overlay','.seasonal-environment'].map(s => Number(getComputedStyle(document.querySelector(s)).zIndex)));
  assert(layers[0] > layers[1]);
  await page.emulateMedia({reducedMotion:'reduce'});
  await visit('seasonal_date=2026-12-24');
  assert.equal(await page.evaluate(() => document.querySelector('.seasonal-environment').getAnimations({subtree:true}).filter(a => a.playState === 'running').length), 0);
  assert.deepEqual(errors, []);
  await browser.close();
  console.log('PASS: 20 layout cases, 8 seasonal dates, alert layers, node budget, reduced motion.');
})().catch(error => { console.error(error); process.exit(1); });
