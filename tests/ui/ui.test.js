// Run with: node --test tests/ui/ui.test.js
const test = require('node:test');
const assert = require('node:assert');
const ui = require('../../web/ui.js');

test('interpolated values are escaped', () => {
  assert.strictEqual(String(ui.html`<p>${'<img onerror=x>'}</p>`), '<p>&lt;img onerror=x&gt;</p>');
  assert.strictEqual(String(ui.html`<p>${ui.html`<b>ok</b>`}</p>`), '<p><b>ok</b></p>');
});

test('unknown is never rendered as zero, and measured zero stays zero', () => {
  assert.strictEqual(ui.fmtNum(null, 'kW'), 'Unknown');
  assert.strictEqual(ui.fmtNum(undefined, 'kW'), 'Unknown');
  assert.strictEqual(ui.fmtNum(0, 'kW'), '0 kW');
});

test('touching hours merge, disjoint hours stay separate', () => {
  const merged = ui.mergeWindows([
    { start: '2026-08-19T05:30:00Z', end: '2026-08-19T06:30:00Z' },
    { start: '2026-08-19T04:30:00Z', end: '2026-08-19T05:30:00Z' },
    { start: '2026-08-19T12:30:00Z', end: '2026-08-19T13:30:00Z' },
  ]);
  assert.deepStrictEqual(merged, [
    { start: '2026-08-19T04:30:00Z', end: '2026-08-19T06:30:00Z' },
    { start: '2026-08-19T12:30:00Z', end: '2026-08-19T13:30:00Z' },
  ]);
  assert.deepStrictEqual(ui.fmtWindows(merged), ['10:00 to 12:00 IST', '18:00 to 19:00 IST']);
});

test('combined execution reasons and late readings are explained', () => {
  const text = ui.fmtReason('PUMP_NOT_OBSERVED_ON,EV_CHARGING_NOT_OBSERVED (late reading)');
  assert.match(text, /pump meter saw no power/);
  assert.match(text, /charging meter saw no power/);
  assert.match(text, /arrived late/);
  assert.match(ui.fmtReason('NEW_CODE'), /NEW_CODE/);
});

test('no status other than an observed match reads as agreement', () => {
  ['UNOBSERVED', 'CLAIMED_EXECUTED', 'AMBIGUOUS', 'STALE', 'OBSERVED_DEVIATION', 'OUTAGE', 'FUTURE_CODE'].forEach((code) => {
    assert.notStrictEqual(ui.fmtStatus(code).tone, 'good', code);
  });
  assert.strictEqual(ui.fmtStatus('OBSERVED_MATCH').tone, 'good');
});

const baseState = (extra) => ({
  clock: { interval_index: 2, horizon_intervals: 96, model_dt_minutes: 15, clock_start_utc: '2026-08-18T18:30:00Z', model_time_utc: '2026-08-18T19:00:00Z' },
  apartment: { model_tank_l: 4000, model_tank_min_l: 3000, ev_sessions: [{ ev_id: 'EV_1', departure_interval: 32, remaining_model_kwh: 10 }] },
  readiness: {},
  pending_proposals: [],
  active_commitment: null,
  execution: null,
  active_advisory: null,
  observation: null,
  ...extra,
});

test('a pending proposal is never given as the action to take', () => {
  const pending = [{ proposal_id: 'p' }];
  assert.strictEqual(ui.recommendation(baseState({ pending_proposals: pending })).title, 'Review the proposal');
  const r = ui.recommendation(baseState({
    pending_proposals: pending,
    active_commitment: { commitment_id: 'c' },
    execution: { next_action: { pump: 'OFF', ev: 'EV_1' } },
  }));
  assert.strictEqual(r.title, 'Keep the pump off, charge EV_1');
  assert.ok(r.why.some((w) => /still your plan/.test(w)));
});

test('aggregate metering leaves remaining EV energy unknown', () => {
  const session = { ev_id: 'EV_1', remaining_model_kwh: 10 };
  assert.strictEqual(ui.evRemaining(baseState({ readiness: { charging_status_by_ev: { EV_1: 'UNVERIFIED' } } }), session), null);
  assert.strictEqual(ui.evRemaining(baseState({ readiness: { charging_status_by_ev: { EV_1: 'PENDING' } } }), session), 10);
});

test('only real shortfalls are reported', () => {
  assert.deepStrictEqual(ui.shortfalls({ ev_shortfall_model_kwh: { EV_1: 0 }, water_shortfall: { intervals_below_reserve: 0, unmet_withdrawal_l: 0 } }), []);
  const out = ui.shortfalls({ ev_shortfall_model_kwh: { EV_1: 13.6 }, water_shortfall: { intervals_below_reserve: 2, unmet_withdrawal_l: 50 } });
  assert.strictEqual(out.length, 3);
  assert.match(out[0], /13\.6 kWh/);
});
