// Drives both real pages in a browser against a running service. Nothing is mocked.
//
//   npm install --prefix <any folder outside the repo> playwright-core
//   set NODE_PATH=<that folder>\node_modules
//   set NW_OPERATOR_CODE=... and NW_MANAGER_CODE=...   (from config/local.json)
//   node tests/ui/e2e_flow.cjs
//
// NW_BASE defaults to http://127.0.0.1:8780. It uses the installed Chrome (NW_CHANNEL to change).
// NW_TTL_BASE: optional second service started with NIVAWATT_PROPOSAL_TTL_S=3, for the expiry check.
// NW_ONLY_TTL=1 runs only that check, for machines short of memory.
// NW_SENSING=0 skips the checks that need the sensing fields from rohan-core PR #4.
const path = require('node:path');
const assert = require('node:assert');
const { chromium } = require('playwright-core');

const BASE = process.env.NW_BASE || 'http://127.0.0.1:8780';
const TTL_BASE = process.env.NW_TTL_BASE;
const SENSING = process.env.NW_SENSING !== '0';
const OP = process.env.NW_OPERATOR_CODE;
const MG = process.env.NW_MANAGER_CODE;
const SHOTS = process.env.NW_SHOTS || path.join(__dirname, 'screenshots');
const PHONE = { viewport: { width: 390, height: 844 }, hasTouch: true, isMobile: true };
const DESK = { viewport: { width: 1280, height: 900 } };

const results = [];
async function check(name, fn) {
  try {
    await fn();
    results.push(['PASS', name]);
    console.log(`PASS  ${name}`);
  } catch (e) {
    results.push(['FAIL', name]);
    console.log(`FAIL  ${name}\n      ${String(e.message).split('\n').slice(0, 4).join('\n      ')}`);
  }
}

const shot = (page, name) => {
  const options = { path: path.join(SHOTS, `${name}.png`), fullPage: true };
  return page.screenshot(options).catch(() => page.waitForTimeout(1000).then(() => page.screenshot(options)));
};
const see = (page, text, timeout = 8000) => page.getByText(text, { exact: false }).first().waitFor({ timeout });
const absent = async (page, text) => assert.strictEqual(await page.getByText(text, { exact: false }).count(), 0, `should not show: ${text}`);
const noSideScroll = async (page) => {
  const [content, view] = await page.evaluate(() => [document.documentElement.scrollWidth, window.innerWidth]);
  assert.ok(content <= view, `page is ${content}px wide in a ${view}px screen`);
};
const bigControls = async (page, scope) => {
  const small = await page.$$eval(`${scope} button, ${scope} select, ${scope} input[type=text], ${scope} input[type=password]`, (els) => els
    .filter((e) => e.offsetParent && !e.classList.contains('bar') && e.getBoundingClientRect().height < 44).map((e) => e.textContent || e.id));
  assert.deepStrictEqual(small, [], 'controls under 44px tall');
};

async function operatorStart(page, base, scenario) {
  await page.selectOption('#scenario', scenario);
  await page.click('#create-run');
  await see(page, 'Run started');
  await page.locator('#advisory-form').waitFor();
  await page.click('#advisory-form button');
  await see(page, 'Advisory issued');
  return page.locator('#manager-link').getAttribute('href');
}

async function operatorStep(page, { pump = 'OFF', ev = 'OFF', reading = 'normal', follow = false } = {}) {
  const before = await page.evaluate(() => document.getElementById('due').innerText.match(/interval (\d+) of/)[1]);
  if (follow) {
    await page.waitForFunction(() => /for this interval: (?!none)/.test(document.getElementById('due').innerText));
    await page.click('#match-plan');
  } else {
    await page.check(`input[name=pump][value=${pump}]`);
    await page.check(`input[name=ev][value=${ev}]`);
  }
  await page.check(`input[name=reading][value=${reading}]`);
  await page.click('#step');
  // A background poll can also redraw this text, so wait for the interval number itself.
  await page.waitForFunction((b) => document.getElementById('due').innerText.match(/interval (\d+) of/)[1] !== b, before);
}

async function managerOpen(ctx, link) {
  const page = await ctx.newPage();
  await page.goto(link);
  await page.fill('#access-code', MG);
  await page.click('#signin-form button');
  await page.locator('#app').waitFor();
  return page;
}
const reload = async (page) => { await page.reload(); await page.locator('#app').waitFor(); };

// Demo sessions are per tab, so each new operator tab signs in and loads the saved forecast.
async function operatorTab(ctx) {
  const page = await ctx.newPage();
  await page.goto(`${BASE}/operator`);
  await page.fill('#access-code', OP);
  await page.click('#signin-form button');
  await page.locator('#app').waitFor();
  await page.waitForFunction(() => document.querySelectorAll('.bar').length === 24);
  return page;
}

(async () => {
  const browser = await chromium.launch({ channel: process.env.NW_CHANNEL || 'chrome' });
  const opCtx = await browser.newContext(DESK);
  const mgCtx = await browser.newContext(PHONE);
  const op = await opCtx.newPage();
  const consoleErrors = [];
  op.on('pageerror', (e) => consoleErrors.push(`operator: ${e.message}`));
  let link;
  let mg;

  if (process.env.NW_ONLY_TTL) {
    await expiryCheck(browser);
    return finish(browser, consoleErrors);
  }

  await check('operator: a wrong access code is refused with a clear message', async () => {
    await op.goto(`${BASE}/operator`);
    await op.fill('#access-code', 'wrong');
    await op.click('#signin-form button');
    await see(op, 'That access code was not accepted');
    assert.ok(await op.locator('#signin').isVisible());
  });

  await check('operator: forecast shows source, scope, issue time and peak hours', async () => {
    await op.fill('#access-code', OP);
    await op.click('#signin-form button');
    await op.locator('#app').waitFor();
    await op.waitForFunction(() => document.getElementById('forecast-start').value);
    await op.click('#forecast-form button');
    await see(op, 'Saved forecast loaded', 90000); // the first load reads the whole dataset
    for (const t of ['Forecast peak hours', 'Karnataka state grid', 'Not BESCOM feeder', 'Historical replay, not a live connection', 'Issued', 'Publication lag', 'Actual, for evaluation only', 'Not a BESCOM or KPTCL system']) await see(op, t);
    assert.strictEqual(await op.locator('.bar').count(), 24);
    await shot(op, 'operator-1-forecast');
  });

  await check('operator: no advisory exists until it is approved', async () => {
    await op.selectOption('#scenario', 'branch');
    await op.click('#create-run');
    await see(op, 'Run started');
    await see(op, 'No advisory is active');
    link = await op.locator('#manager-link').getAttribute('href');
    const p = await managerOpen(mgCtx, link);
    await see(p, 'No action yet');
    await see(p, 'No advisory has been issued');
    await p.close();
    await op.click('#advisory-form button');
    await see(op, 'Advisory issued');
    await see(op, 'Approved by');
    await shot(op, 'operator-2-advisory-issued');
  });

  await check('manager: advisory, allowance, tank, charging and proposal are shown on a phone', async () => {
    mg = await managerOpen(mgCtx, link);
    mg.on('pageerror', (e) => consoleErrors.push(`manager: ${e.message}`));
    for (const t of ['Peak advisory', 'kW (model)', 'participating flexible loads', 'Water tank', 'Requested', 'Deadline', 'Version', 'not active', 'The operator issued a peak advisory', 'Utility smart meter', 'Not connected', 'Review the proposal']) await see(mg, t);
    await noSideScroll(mg);
    await bigControls(mg, '#app');
    await shot(mg, 'manager-1-proposal');
  });

  await check('acceptance: accepted is not done, and nothing reports as executed', async () => {
    await mg.click('button[data-act=accept]');
    await see(mg, 'Nothing has been switched');
    await see(mg, 'Accepted does not mean done');
    await see(mg, 'Not checked yet');
    await absent(mg, 'Sensors agree');
    await shot(mg, 'manager-2-accepted');
  });

  await check('done tap: records a report only, and a double tap makes one report', async () => {
    const button = mg.locator('button[data-act=claim]').first();
    await button.dblclick();
    await see(mg, 'Sensors have not confirmed it');
    await see(mg, 'Sensors have not checked your latest report');
    await see(mg, 'Reported, waiting for sensors');
    await absent(mg, 'Sensors agree');
    await mg.waitForFunction(() => /Reports made\s*1\b/.test(document.getElementById('execution').innerText));
    await shot(mg, 'manager-3-done-reported');
  });

  await check('contradiction: sensors disagree, the report stays, and the revision is not active', async () => {
    await operatorStep(op, { pump: 'OFF', ev: 'OFF' });
    await reload(mg);
    await see(mg, 'Sensors disagree');
    await see(mg, 'the charging meter saw no power');
    await see(mg, 'You reported');
    await mg.waitForFunction(() => document.querySelector('.said li'));
    await see(mg, 'An action was reported done, but sensors did not see it happen');
    await see(mg, 'Until you accept it, this is still your plan');
    await mg.waitForFunction(() => /contradicted by sensors\s*1\b/.test(document.getElementById('execution').innerText));
    await noSideScroll(mg);
    await shot(mg, 'manager-4-contradicted-revision');
    await shot(op, 'operator-3-deviation');
  });

  await check('revision: accepted, then performed, and sensors agree with the outcome counted', async () => {
    await mg.click('button[data-act=accept]');
    await see(mg, 'Plan accepted');
    await see(mg, 'No proposal is open');
    await op.waitForTimeout(100);
    await operatorStep(op, { follow: true });
    await reload(mg);
    await see(mg, 'Sensors agree');
    await see(mg, 'Delivered, verified');
    const text = await mg.locator('#charging').innerText();
    assert.match(text, /Delivered, verified\s*0\.83 kWh/);
    await shot(mg, 'manager-5-observed-match');
    await see(op, 'Run outcome');
    await see(op, 'simulator truth');
    await shot(op, 'operator-4-outcome');
  });

  await check('stale proposal: acting on an old version is refused, and state refreshes', async () => {
    const other = await managerOpen(mgCtx, link);
    await other.click('#charging summary');
    await other.fill('#charging input[name=kwh]', '12');
    await other.click('#charging .req-form button');
    await see(other, 'New proposal requested');
    await reload(mg);
    await mg.locator('button[data-act=accept]').waitFor();
    // Replace the proposal behind this screen, then accept what it still shows.
    await other.click('#charging summary');
    await other.fill('#charging input[name=kwh]', '13');
    await other.click('#charging .req-form button');
    await other.waitForFunction(() => document.getElementById('toast').innerText.includes('New proposal requested'));
    await mg.click('button[data-act=accept]');
    await see(mg, 'This proposal is no longer open');
    await mg.locator('button[data-act=accept]').waitFor();
    await other.close();
  });

  await check('shortfall: an impossible request shows a quantified warning, not success', async () => {
    await mg.click('#charging summary');
    await mg.fill('#charging input[name=kwh]', '400');
    await mg.click('#charging .req-form button');
    await see(mg, 'Service shortfall');
    await see(mg, 'short of its request');
    await shot(mg, 'manager-6-shortfall');
    await mg.click('button[data-act=decline]');
    await see(mg, 'Proposal declined');
    await see(mg, 'No proposal is open');
    await see(mg, 'Accepted plan');
  });

  await check('missing reading: shows unknown, never zero', async () => {
    await operatorStep(op, { follow: true, reading: 'missing' });
    await reload(mg);
    await see(mg, 'No reading');
    await see(mg, 'Unknown now');
    await see(mg, 'Reserve unknown');
    const readings = await mg.locator('#readings').innerText();
    assert.match(readings, /Combined power\s*Unknown/);
    assert.match(readings, /Pump power\s*Unknown/);
    await see(op, 'They are unknown, not zero');
    await shot(mg, 'manager-7-missing-reading');
  });

  if (SENSING) {
    await check('late reading: shown as arrived late, never as live', async () => {
      await operatorStep(op, { follow: true, reading: 'delayed' });
      await see(op, 'No reading');
      await operatorStep(op, { follow: true });
      await see(op, 'from a late reading');
      await shot(op, 'operator-5-late-reading');
    });

    await check('aggregate-only meter: cannot tell, with no per-EV credit', async () => {
      const a = await operatorTab(opCtx);
      const l = await operatorStart(a, BASE, 'aggregate');
      const m = await managerOpen(mgCtx, l);
      await m.click('button[data-act=accept]');
      await see(m, 'Plan accepted');
      await operatorStep(a, { follow: true });
      await reload(m);
      await see(m, 'Cannot tell');
      await see(m, 'cannot tell whether it came from the pump or the charger');
      await see(m, 'cannot be attributed to an EV');
      const charging = await m.locator('#charging').innerText();
      assert.match(charging, /Delivered, verified\s*Unknown/);
      assert.match(charging, /Still to deliver\s*Unknown/);
      assert.match(await m.locator('#tank').innerText(), /Pump seen as:\s*Unknown/);
      assert.match(await m.locator('#readings').innerText(), /One combined meter/);
      await absent(m, 'Sensors agree');
      await shot(m, 'manager-8-aggregate-only');
      await m.close();
      await a.close();
    });
  }

  await check('pump without water: power alone is not accepted as delivery', async () => {
    const d = await operatorTab(opCtx);
    const l = await operatorStart(d, BASE, 'dry');
    const m = await managerOpen(mgCtx, l);
    await m.click('button[data-act=accept]');
    await see(m, 'Plan accepted');
    for (let n = 0; n < 96; n += 1) {
      await d.waitForFunction(() => /for this interval: (?!none)/.test(document.getElementById('due').innerText));
      const due = await d.locator('#due').innerText();
      await operatorStep(d, { follow: true });
      if (/Turn the pump on/.test(due)) break;
    }
    await reload(m);
    await see(m, 'Sensors disagree');
    await see(m, 'the tank did not rise');
    await shot(m, 'manager-9-pump-without-water');
    await m.close();
    await d.close();
  });

  await check('authorization: an invalid session returns to sign-in with a reason', async () => {
    const p = await managerOpen(mgCtx, link);
    await p.evaluate(() => sessionStorage.setItem('nivawatt.session.manager', 'not-a-real-session'));
    await p.reload();
    await see(p, 'Your demo session has ended');
    assert.ok(await p.locator('#signin').isVisible());
    await p.close();
  });

  await check('unknown run: says so instead of showing an empty apartment', async () => {
    const p = await mgCtx.newPage();
    await p.goto(`${BASE}/manager?run=run-does-not-exist`);
    await p.fill('#access-code', MG);
    await p.click('#signin-form button');
    await see(p, 'No run has that ID');
    await p.close();
  });

  await check('phone: operator page has no sideways scroll and large controls', async () => {
    const ctx = await browser.newContext(PHONE);
    const p = await ctx.newPage();
    await p.goto(`${BASE}/operator?run=${new URL(link).searchParams.get('run')}`);
    await p.fill('#access-code', OP);
    await p.click('#signin-form button');
    await p.locator('#app').waitFor();
    await p.waitForFunction(() => document.getElementById('forecast-start').value);
    await p.click('#forecast-form button');
    await p.waitForFunction(() => document.querySelectorAll('.bar').length === 24);
    await see(p, 'Participating apartments');
    await noSideScroll(p);
    await bigControls(p, '#app');
    await shot(p, 'operator-6-phone');
    await ctx.close();
  });

  if (TTL_BASE) await expiryCheck(browser);
  await finish(browser, consoleErrors);
})();

async function expiryCheck(browser) {
  await check('expired proposal: refused by the server, and the screen says it closed', async () => {
    const ctx = await browser.newContext(DESK);
    const o = await ctx.newPage();
    await o.goto(`${TTL_BASE}/operator`);
    await o.fill('#access-code', OP);
    await o.click('#signin-form button');
    await o.locator('#app').waitFor();
    await o.waitForFunction(() => document.getElementById('forecast-start').value);
    await o.click('#forecast-form button');
    await see(o, 'Saved forecast loaded', 90000);
    const l = await operatorStart(o, TTL_BASE, 'branch');
    const m = await managerOpen(await browser.newContext(PHONE), l);
    await m.locator('button[data-act=accept]').waitFor();
    await m.waitForTimeout(3500);
    await m.click('button[data-act=accept]');
    await see(m, 'This proposal is no longer open');
    await see(m, 'No plan is accepted yet');
    await see(m, 'Request a new proposal');
    await ctx.close();
  });
}

async function finish(browser, consoleErrors) {
  await check('no uncaught script errors on either page', async () => {
    assert.deepStrictEqual(consoleErrors, []);
  });
  await browser.close();
  const failed = results.filter(([s]) => s === 'FAIL').length;
  console.log(`\n${results.length - failed} passed, ${failed} failed`);
  process.exit(failed ? 1 : 0);
}
