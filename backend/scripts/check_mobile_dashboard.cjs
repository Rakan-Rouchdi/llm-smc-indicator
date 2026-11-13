// Run only against the isolated preview server. Never load production credentials.
const { chromium } = require('playwright');
const fs = require('node:fs/promises');
const path = require('node:path');
const assert = require('node:assert/strict');

async function main() {
  const base = process.argv[2] || 'http://127.0.0.1:8014';
  const output = process.argv[3] || '/tmp/smc-mobile-check';
  const fixture = process.argv[4];
  const url = new URL(base);
  assert(['localhost', '127.0.0.1'].includes(url.hostname), 'Only isolated local previews are allowed');
  await fs.mkdir(output, {recursive: true});
  const browser = await chromium.launch({headless: true, channel: 'chrome'});
  const results = [];
  try {
    for (const width of [320, 390, 768, 1440]) {
      const page = await browser.newPage({viewport: {width, height: 844}});
      const errors = [];
      page.on('pageerror', error => errors.push(error.message));
      // Never permit a preview to send requests to real services.
      await page.route('**/*', route => new URL(route.request().url()).origin === url.origin
        ? route.continue() : route.abort());
      const routes = ['/dashboard', '/dashboard/setups/4', '/dashboard/forward-testing'];
      for (const route of routes) {
        assert.equal((await page.goto(base + route)).status(), 200);
        const dimensions = await page.evaluate(() => ({width: innerWidth, scroll: document.documentElement.scrollWidth}));
        assert.equal(dimensions.width, width, 'Viewport override did not apply');
        assert(dimensions.scroll <= width, `Page overflow: ${width} ${route}`);
        await page.screenshot({path: path.join(output, `${width}-${route.split('/').pop()}.png`), fullPage: true});
        results.push({route, ...dimensions});
      }
      if (fixture) {
        await page.route('**/dashboard/forward-testing', route => route.fulfill({contentType: 'text/html', path: fixture}));
        await page.goto(base + '/dashboard/forward-testing');
        await page.getByText('Record paper outcome', {exact: true}).click();
        await page.locator('[name="observed_until"]').fill('2026-11-13T18:00');
        await page.locator('[name="notes"]').fill('Synthetic UI evidence; not a market observation.');
        const requestBody = [];
        await page.route('**/forward-testing/decisions/*/reviews', route => {
          requestBody.push(route.request().postDataJSON());
          return route.fulfill({status: 422, contentType: 'application/json', body: JSON.stringify({detail: 'Synthetic validation error'})});
        });
        await page.getByRole('button', {name: 'Save paper review'}).click();
        await page.getByRole('status').filter({hasText: 'Synthetic validation error'}).waitFor();
        assert.equal(requestBody[0].outcome, 'UNKNOWN');
        assert.equal(requestBody[0].source_verified, false);
        assert.equal(await page.getByRole('button', {name: 'Save paper review'}).isEnabled(), true);
        assert.equal(await page.evaluate(() => document.documentElement.scrollWidth), width);
        await page.screenshot({path: path.join(output, `${width}-review-form.png`), fullPage: true});
      }
      assert.deepEqual(errors, []);
      await page.close();
    }
    await fs.writeFile(path.join(output, 'measurements.json'), JSON.stringify(results, null, 2));
    console.log(JSON.stringify({passed: results.length, widths: [320, 390, 768, 1440], formChecked: Boolean(fixture), output}));
  } finally { await browser.close(); }
}
main().catch(error => { console.error(error.message); process.exitCode = 1; });
