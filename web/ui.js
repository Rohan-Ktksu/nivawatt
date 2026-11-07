// Display helpers shared by both views. Everything here formats server values; nothing computes a
// schedule or a metric. Unknown stays unknown: null never renders as zero.
const NW_UI = (() => {
  const ENTITIES = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };
  const esc = (v) => String(v).replace(/[&<>"']/g, (c) => ENTITIES[c]);

  class Safe { constructor(s) { this.s = s; } toString() { return this.s; } }
  const piece = (v) => {
    if (v === null || v === undefined || v === false || v === true) return '';
    if (v instanceof Safe) return v.s;
    if (Array.isArray(v)) return v.map(piece).join('');
    return esc(v);
  };
  // Tagged template: every interpolated value is escaped unless it is already html``.
  const html = (strings, ...values) => new Safe(strings.reduce((out, s, i) => out + s + (i < values.length ? piece(values[i]) : ''), ''));

  const IST = { timeZone: 'Asia/Kolkata' };
  const dateTime = new Intl.DateTimeFormat('en-IN', { ...IST, day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit', hour12: false });
  const clock = new Intl.DateTimeFormat('en-IN', { ...IST, hour: '2-digit', minute: '2-digit', hour12: false });
  const fmtTime = (iso) => (iso ? `${dateTime.format(new Date(iso))} IST` : 'Unknown');
  const fmtClock = (iso) => (iso ? clock.format(new Date(iso)) : 'Unknown');

  // Touching forecast hours read as one span; disjoint hours stay separate.
  function mergeWindows(windows) {
    const out = [];
    [...(windows || [])].sort((a, b) => a.start.localeCompare(b.start)).forEach((w) => {
      const last = out[out.length - 1];
      if (last && new Date(last.end).getTime() === new Date(w.start).getTime()) last.end = w.end;
      else out.push({ ...w });
    });
    return out;
  }
  const fmtWindows = (windows) => mergeWindows(windows).map((w) => `${fmtClock(w.start)} to ${fmtClock(w.end)} IST`);

  const inWindows = (iso, windows) => {
    const t = new Date(iso).getTime();
    return (windows || []).some((w) => new Date(w.start).getTime() <= t && t < new Date(w.end).getTime());
  };

  const intervalTime = (c, i) => new Date(new Date(c.clock_start_utc).getTime() + i * c.model_dt_minutes * 60000).toISOString();

  function fmtNum(v, unit, digits = 2) {
    if (v === null || v === undefined) return 'Unknown';
    const n = Number(v).toLocaleString('en-IN', { maximumFractionDigits: digits });
    return unit ? `${n} ${unit}` : n;
  }

  const SOURCES = {
    synthetic: 'Synthetic simulation, not a measurement',
    synthetic_simulation: 'Synthetic simulation, not a measurement',
    hardware: 'Bench hardware measurement (raw units)',
    scaled_hardware: 'Scaled from the bench. A model value, not a field measurement',
    historical_replay: 'Historical replay, not a live connection',
  };
  const fmtSource = (kind) => SOURCES[kind] || `Unrecognised source: ${kind || 'not stated'}`;

  const REASONS = {
    PUMP_NOT_OBSERVED_ON: 'The pump was due on, but the pump meter saw no power.',
    PUMP_POWER_WITHOUT_WATER_DELIVERY: 'The pump drew power, but the tank did not rise. Power alone does not prove water was delivered.',
    PUMP_WATER_DELIVERY_NOT_OBSERVED: 'The pump was due on, but the tank sensor saw no rise in water.',
    PUMP_ON_NOT_PLANNED: 'The pump was running when the plan had it off.',
    EV_CHARGING_NOT_OBSERVED: 'Charging was due, but the charging meter saw no power.',
    EV_CHARGING_NOT_PLANNED: 'Charging was running when the plan had it off.',
    NO_PARTICIPATING_LOAD_OBSERVED: 'An action was due, but the combined meter read zero, so nothing was running.',
    AGGREGATE_ONLY_BRANCH_UNATTRIBUTED: 'The combined meter saw power, but cannot tell whether it came from the pump or the charger.',
  };
  function fmtReason(reason) {
    if (!reason) return '';
    const late = /\s*\(late reading\)\s*$/.test(reason);
    const codes = reason.replace(/\s*\(late reading\)\s*$/, '').split(',').map((c) => c.trim()).filter(Boolean);
    const text = codes.map((c) => REASONS[c] || `Reason code ${c}.`).join(' ');
    return late ? `${text} This came from a reading that arrived late.`.trim() : text;
  }

  const STATUSES = {
    UNOBSERVED: { icon: '…', tone: 'unknown', label: 'Not checked yet', detail: 'No sensor reading covers this commitment yet.' },
    CLAIMED_EXECUTED: { icon: '…', tone: 'unknown', label: 'Reported only', detail: 'A report is not a measurement.' },
    OBSERVED_MATCH: { icon: '✓', tone: 'good', label: 'Sensors agree', detail: 'The readings for this interval match the plan.' },
    OBSERVED_DEVIATION: { icon: '✕', tone: 'bad', label: 'Sensors disagree', detail: 'The readings for this interval do not match the plan.' },
    AMBIGUOUS: { icon: '?', tone: 'unknown', label: 'Cannot tell', detail: 'The reading is consistent with more than one switch position.' },
    STALE: { icon: '?', tone: 'unknown', label: 'No reading', detail: 'No valid reading has arrived for this interval. Missing is not the same as zero.' },
    OUTAGE: { icon: '!', tone: 'warn', label: 'Outage', detail: 'An outage covers this interval.' },
  };
  const fmtStatus = (code) => STATUSES[code] || { icon: '?', tone: 'unknown', label: code || 'Unknown', detail: '' };

  const REVISION_REASONS = {
    PEAK_ADVISORY_ISSUED: 'The operator issued a peak advisory.',
    ALLOWANCE_CHANGED: 'The operator changed the participating-load allowance.',
    OUTAGE_ANNOUNCED: 'The operator announced a water source outage.',
    REQUIREMENT_CHANGED: 'The charging requirement was updated.',
    OBSERVED_DEVIATION: 'Sensors saw something different from the accepted plan.',
    CLAIM_WITHOUT_OBSERVED_EXECUTION: 'An action was reported done, but sensors did not see it happen.',
  };
  const fmtRevisionReason = (code) => REVISION_REASONS[code] || `Reason code ${code}.`;

  const QUALITY = {
    VALID: { icon: '✓', tone: 'good', label: 'On time', detail: 'Arrived in the interval it describes.' },
    LATE: { icon: '!', tone: 'warn', label: 'Arrived late', detail: 'A real reading, delivered after its interval. It is not live.' },
    STALE: { icon: '?', tone: 'unknown', label: 'Missing', detail: 'No reading for this interval. Values are unknown, not zero.' },
  };
  const fmtQuality = (q) => QUALITY[q] || { icon: '?', tone: 'unknown', label: q || 'No reading yet', detail: 'No reading has arrived yet.' };

  const fmtScope = (scope) => ({
    branch: 'Separate pump and charger meters, plus a tank sensor',
    aggregate: 'One combined meter, plus a tank sensor. It cannot prove which load ran',
  }[scope] || 'Not stated by the service');

  // Device runs send an interval summary; a reading posted to a simulator run arrives as one raw sample.
  function fmtRawBench(raw) {
    if (!raw) return null;
    if (raw.sample_count === undefined) return `One reading from ${raw.device_id || 'an unnamed device'}, in raw device units.`;
    const ignored = raw.excluded_samples ? ` ${raw.excluded_samples} duplicate or out-of-order ignored.` : '';
    if (!raw.sample_count) return `No readings arrived for this interval.${ignored}`;
    const count = `${fmtNum(raw.sample_count)} ${raw.sample_count === 1 ? 'reading' : 'readings'}.`;
    const branches = raw.mean_pump_w === null && raw.mean_ev_load_w === null
      ? `Mean combined ${fmtNum(raw.mean_aggregate_w, 'W')}.`
      : `Mean pump ${fmtNum(raw.mean_pump_w, 'W')}, mean charger ${fmtNum(raw.mean_ev_load_w, 'W')}.`;
    return `${count} ${branches}${ignored}`;
  }

  function fmtAction(action) {
    if (!action) return 'No action scheduled';
    const pump = action.pump === 'ON' ? 'Turn the pump on' : 'Keep the pump off';
    const ev = action.ev && action.ev !== 'OFF' ? `charge ${action.ev}` : 'keep charging off';
    return `${pump}, ${ev}`;
  }

  // The recommended next action comes from the accepted commitment only. A pending proposal is never advice to act on.
  function recommendation(state) {
    const pending = state.pending_proposals || [];
    const commitment = state.active_commitment;
    const ended = state.clock.interval_index >= state.clock.horizon_intervals;
    if (ended) return { title: 'This run has finished', why: ['The simulated day is over. See the outcome below.'] };
    if (!commitment) {
      if (pending.length) return { title: 'Review the proposal', why: ['Nothing applies until you accept it. Accepting does not switch any equipment.'] };
      if (!state.active_advisory) return { title: 'No action yet', why: ['The operator has not issued a peak advisory for this run.'] };
      return { title: 'Request a new proposal', why: ['There is no accepted plan and no open proposal. Use the charging requirement form to request one.'] };
    }
    const action = state.execution?.next_action;
    const why = [];
    const a = state.apartment;
    if (action?.pump === 'ON') why.push(`The tank is at ${fmtNum(a.model_tank_l, 'L', 0)} and the plan refills it to stay above the ${fmtNum(a.model_tank_min_l, 'L', 0)} reserve.`);
    if (action?.ev && action.ev !== 'OFF') {
      const s = a.ev_sessions.find((x) => x.ev_id === action.ev);
      if (s) why.push(`${s.ev_id} needs charging before ${fmtClock(intervalTime(state.clock, s.departure_interval))} IST.`);
    }
    if (action && action.pump !== 'ON' && (!action.ev || action.ev === 'OFF')) {
      why.push(inWindows(state.clock.model_time_utc, state.active_advisory?.peak_windows)
        ? 'This is an advisory peak hour and nothing needs to run.'
        : 'The accepted plan has nothing to run in this interval.');
    }
    if (state.observation && fmtQuality(state.observation.quality).tone === 'unknown') why.push('The latest reading is missing, so this advice relies on the last valid reading.');
    if (pending.length) why.push('A newer proposal is waiting below. Until you accept it, this is still your plan.');
    return { title: fmtAction(action), why };
  }

  // Shortfalls exactly as the scheduler quantified them.
  function shortfalls(option) {
    if (!option) return [];
    const out = [];
    Object.entries(option.ev_shortfall_model_kwh || {}).forEach(([ev, kwh]) => {
      if (kwh > 0) out.push(`${ev} would leave ${fmtNum(kwh, 'kWh (model)')} short of its request.`);
    });
    const w = option.water_shortfall || {};
    if (w.intervals_below_reserve > 0) out.push(`The tank would be below reserve for ${w.intervals_below_reserve} intervals.`);
    if (w.unmet_withdrawal_l > 0) out.push(`${fmtNum(w.unmet_withdrawal_l, 'L', 0)} of water demand would go unmet.`);
    return out;
  }

  const fmtError = (e) => ({
    STALE_PROPOSAL: 'This proposal is no longer open. Its version changed, or it expired or was replaced. The screen now shows the latest state.',
    WRONG_RUN: 'This proposal belongs to a different run. The screen now shows the latest state.',
    OPERATOR_EXCEPTION_REQUIRED: 'This option goes over the allowance, so only the operator can decide it.',
    CLAIM_OUT_OF_RANGE: 'That interval is outside the current commitment. The screen now shows the latest state.',
    RUN_FINISHED: 'This run has reached the end of its simulated day. Create a new run to continue.',
    UNAUTHENTICATED: 'Your demo session has ended. Sign in again.',
    INVALID_ACCESS_CODE: 'That access code was not accepted. Check it and try again.',
    FORBIDDEN_ROLE: 'This session does not have permission for that action.',
    FORBIDDEN_APARTMENT: 'This session belongs to another apartment.',
    UNKNOWN_RUN: 'No run has that ID. Check the run link from the operator.',
    UNKNOWN_APARTMENT: 'That apartment is not part of this run. Check the apartment ID.',
    DATASET_UNAVAILABLE: 'The demand dataset is not on this computer. Run scripts/fetch_kptcl.py, then restart the service.',
  }[e.code] || e.message);

  return { esc, html, fmtTime, fmtClock, mergeWindows, fmtWindows, inWindows, intervalTime, fmtNum, fmtSource, fmtReason, fmtStatus, fmtRevisionReason, fmtQuality, fmtScope, fmtRawBench, fmtAction, recommendation, shortfalls, fmtError };
})();

if (typeof module !== 'undefined') module.exports = NW_UI;
