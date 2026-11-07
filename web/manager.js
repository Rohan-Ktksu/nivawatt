(() => {
  const { html, fmtTime, fmtClock, fmtWindows, inWindows, intervalTime, fmtNum, fmtSource, fmtReason, fmtStatus, fmtRevisionReason, fmtQuality, fmtScope, fmtAction, evRemaining, recommendation, shortfalls, fmtError } = NW_UI;
  const $ = (id) => document.getElementById(id);
  const POLL_MS = 5000;

  const params = new URLSearchParams(location.search);
  const store = {
    get: (k) => { try { return localStorage.getItem(k); } catch { return null; } },
    set: (k, v) => { try { localStorage.setItem(k, v); } catch { /* the form asks again next time */ } },
  };
  let runId = params.get('run') || store.get('nivawatt.manager.run') || '';
  let apartmentId = store.get('nivawatt.manager.apartment') || 'APT_1';
  let state = null;
  let report = null;
  let reportKey = null;
  let lastJson = null;
  let lastUpdated = null;
  let shownProposal = null;
  let connectionWarned = false;
  const deliveredSent = new Set();

  let toastTimer;
  const toast = (tone, message) => {
    clearTimeout(toastTimer);
    $('toast').innerHTML = message ? String(html`<div class="notice tone-${tone}"><p>${message}</p></div>`) : '';
    if (tone === 'good') toastTimer = setTimeout(() => toast(), 8000);
  };
  const chip = (s) => html`<span class="chip tone-${s.tone}"><span aria-hidden="true">${s.icon}</span>${s.label}</span>`;
  const put = (id, content) => { $(id).innerHTML = String(content); };
  const attr = (s) => html([s]);

  function showSignIn(message) {
    $('app').hidden = true;
    $('loading').hidden = true;
    $('signin').hidden = false;
    $('run-id').value = runId;
    $('apartment-id').value = apartmentId;
    if (message) toast('bad', message);
  }

  function optionSummary(option, clock, peakWindows) {
    const upcoming = option.actions.filter((a) => a.interval_index >= clock.interval_index && (a.pump === 'ON' || a.ev !== 'OFF')).slice(0, 8);
    return html`
      <dl class="facts">
        <dt>Highest load</dt><dd>${fmtNum(option.predicted_peak_model_kw, 'kW (model)')}</dd>
        <dt>Load in peak hours</dt><dd>${fmtNum(option.predicted_peak_window_energy_model_kwh, 'kWh (model)')}</dd>
        <dt>Lowest tank level</dt><dd>${fmtNum(option.predicted_min_tank_model_l, 'L', 0)}</dd>
        <dt>Pump starts planned</dt><dd>${fmtNum(option.pump_starts?.planned)}</dd>
      </dl>
      <h3>Next planned actions</h3>
      ${upcoming.length ? html`<div class="strip">${upcoming.map((a) => {
        const t = intervalTime(clock, a.interval_index);
        return html`<div class="${inWindows(t, peakWindows) ? 'peak' : ''}"><b>${fmtClock(t)}</b>${a.pump === 'ON' ? 'Pump on' : ''}${a.pump === 'ON' && a.ev !== 'OFF' ? ', ' : ''}${a.ev !== 'OFF' ? `Charge ${a.ev}` : ''}${inWindows(t, peakWindows) ? ' (peak)' : ''}</div>`;
      })}</div>` : html`<p>Nothing else is scheduled to run.</p>`}
      ${shortfalls(option).map((s) => html`<div class="notice tone-bad"><p><strong>Service shortfall.</strong> ${s}</p></div>`)}`;
  }

  function renderNext() {
    const r = recommendation(state);
    put('next', html`
      <div class="label">Recommended next action, model time ${fmtTime(state.clock.model_time_utc)}</div>
      <div class="big">${r.title}</div>
      ${r.why.map((w) => html`<p>${w}</p>`)}
      <p class="label">Switching is manual. NivaWatt does not operate any equipment.</p>`);
  }

  function renderCommitment() {
    const c = state.active_commitment;
    if (!c) {
      put('commitment', html`<h2>Accepted plan</h2><p>No plan is accepted yet.</p>`);
      return;
    }
    put('commitment', html`
      <h2>Accepted plan</h2>
      <p><span class="chip tone-good"><span aria-hidden="true">✓</span>Accepted ${fmtTime(c.accepted_at)}</span></p>
      <p class="muted">Applies from ${fmtTime(intervalTime(state.clock, c.effective_from_interval))} model time. Accepted does not mean done.</p>
      ${optionSummary(c.option, state.clock, state.active_advisory?.peak_windows)}`);
  }

  function renderProposal() {
    const p = (state.pending_proposals || [])[0];
    if (!p) {
      put('proposal', html`<h2>Proposal waiting for you</h2><p>No proposal is open.</p>`);
      return;
    }
    const option = p.options[0];
    const blocked = !option || option.requires_operator_exception;
    put('proposal', html`
      <h2>Proposal waiting for you</h2>
      <p><span class="chip tone-warn"><span aria-hidden="true">!</span>Version ${p.revision}, not active</span></p>
      <p><strong>Why now:</strong> ${fmtRevisionReason(p.reason)}</p>
      <p class="muted">Closes at <span data-expires="${p.expires_at}"></span>. Worked out by ${p.source === 'rules' ? 'fixed scheduling rules, not an optimiser' : p.source}.</p>
      ${(p.infeasibilities || []).map((x) => html`<div class="notice tone-bad"><p><strong>Cannot be fully met.</strong> ${typeof x === 'string' ? x : x.message || JSON.stringify(x)}</p></div>`)}
      ${option ? optionSummary(option, state.clock, state.active_advisory?.peak_windows) : html`<p>This proposal has no option to accept.</p>`}
      ${option?.requires_operator_exception ? html`<div class="notice tone-warn"><p>This option goes over the allowance. Only the operator can approve that.</p></div>` : ''}
      <div class="buttons">
        <button class="primary" data-act="accept" ${blocked ? attr('disabled') : ''}>Accept plan</button>
        <button class="decline" data-act="decline" ${option ? '' : attr('disabled')}>Decline</button>
      </div>
      <p class="muted">Accepting records your decision for this version. It does not switch anything.</p>`);
  }

  function renderExecution() {
    const ex = state.execution;
    const i = state.clock.interval_index;
    const action = ex?.next_action;
    const claims = ex?.claims || [];
    const due = [];
    if (action?.pump === 'ON') due.push({ kind: 'pump', label: 'I turned the pump on' });
    if (action?.ev && action.ev !== 'OFF') due.push({ kind: 'ev', label: `I started charging ${action.ev}` });
    const claimedNow = (kind) => claims.some((c) => c.interval_index === i && c.action_id.endsWith(`:${kind}`));
    const checked = ex?.interval_index;
    const claimsForChecked = claims.filter((c) => c.interval_index === checked);
    const status = fmtStatus(ex?.observation_status || 'UNOBSERVED');
    const waiting = claims.filter((c) => checked === null || checked === undefined || c.interval_index > checked);

    put('execution', html`
      <h2>What happened</h2>
      ${ex ? html`
        <div class="ledger">
          <div class="said">
            <h3>You reported</h3>
            ${claimsForChecked.length || waiting.length ? html`<ul>
              ${[...claimsForChecked, ...waiting].map((c) => html`<li>${c.action_id.endsWith(':pump') ? 'Pump on' : 'Charging on'} for ${fmtClock(intervalTime(state.clock, c.interval_index))}, reported ${fmtTime(c.claimed_at)}</li>`)}
            </ul>` : html`<p>Nothing reported for the last checked interval.</p>`}
            <p class="muted">A report is your word. It does not count as done.</p>
          </div>
          <div>
            <h3>Sensors saw</h3>
            <p>${chip(status)}</p>
            ${checked !== null && checked !== undefined ? html`<p class="muted">For ${fmtClock(intervalTime(state.clock, checked))} model time</p>` : ''}
            <p>${fmtReason(ex.reason) || status.detail}</p>
          </div>
        </div>
        ${waiting.length ? html`<div class="notice tone-unknown"><p><span aria-hidden="true">… </span>Sensors have not checked your latest report yet.</p></div>` : ''}
        <h3>Report what you did for ${fmtClock(state.clock.model_time_utc)}</h3>
        ${due.length ? html`
          <div class="buttons">
            ${due.map((d) => html`<button class="claim" data-act="claim" data-kind="${d.kind}" ${claimedNow(d.kind) ? attr('disabled') : ''}>${claimedNow(d.kind) ? 'Reported, waiting for sensors' : d.label}</button>`)}
          </div>
          <p class="muted">This records your report only. Sensors check it separately.</p>`
        : html`<p>Nothing is due in this interval, so there is nothing to report.</p>`}
      ` : html`<p>Accept a plan to start reporting. Sensors check each interval independently.</p>`}
      ${report ? html`
        <h3>So far in this run</h3>
        <dl class="facts">
          <dt>Reports made</dt><dd>${fmtNum(report.counts?.claims)}</dd>
          <dt>Reports contradicted by sensors</dt><dd>${fmtNum(report.counts?.claims_contradicted)}</dd>
          <dt>Intervals with sensor deviation</dt><dd>${fmtNum(report.counts?.observed_deviations)}</dd>
          <dt>Plans proposed / accepted</dt><dd>${fmtNum(report.counts?.proposals)} / ${fmtNum(report.counts?.acceptances)}</dd>
          <dt>Intervals with a usable reading</dt><dd>${fmtNum(report.observation_coverage?.valid)} of ${fmtNum(report.observation_coverage?.intervals_elapsed)}${report.observation_coverage?.late ? `, ${report.observation_coverage.late} late` : ''}</dd>
        </dl>` : ''}`);
  }

  function renderTank() {
    const a = state.apartment;
    const obs = state.observation;
    const missing = obs && obs.tank_l === null;
    const max = a.model_tank_max_l || 1;
    const pct = (v) => Math.max(0, Math.min(100, (v / max) * 100));
    const reserve = {
      ABOVE_MINIMUM: { icon: '✓', tone: 'good', label: 'Above reserve' },
      BELOW_MINIMUM: { icon: '✕', tone: 'bad', label: 'Below reserve' },
      UNKNOWN: { icon: '?', tone: 'unknown', label: 'Reserve unknown' },
    }[state.readiness.water_reserve_status] || { icon: '?', tone: 'unknown', label: 'Reserve unknown' };
    put('tank', html`
      <h2>Water tank</h2>
      <div class="tank-row">
        <div class="tank ${missing ? 'unknown' : ''}" role="img" aria-label="${missing ? 'Tank level unknown' : `Tank at ${fmtNum(a.model_tank_l, 'litres', 0)} of ${fmtNum(max, 'litres', 0)}`}">
          <div class="water" style="height:${pct(a.model_tank_l)}%"></div>
          <div class="reserve" style="bottom:${pct(a.model_tank_min_l)}%"></div>
        </div>
        <div>
          <p class="big">${missing ? 'Unknown now' : fmtNum(a.model_tank_l, 'L', 0)}</p>
          ${missing ? html`<p>Last valid reading ${fmtNum(a.model_tank_l, 'L', 0)}.</p>` : ''}
          <p>${chip(reserve)}</p>
          <p class="muted">Dashed line marks the ${fmtNum(a.model_tank_min_l, 'L', 0)} reserve. Tank holds ${fmtNum(max, 'L', 0)}.</p>
          <p>Pump seen as: <strong>${a.pump_state === 'UNKNOWN' ? 'Unknown' : a.pump_state}</strong></p>
          ${a.source_water_available ? '' : html`<div class="notice tone-warn"><p>The operator announced no source water for this interval.</p></div>`}
        </div>
      </div>`);
  }

  function renderCharging() {
    const a = state.apartment;
    const c = state.clock;
    const r = state.readiness;
    const sessions = a.ev_sessions.map((s) => {
      const remaining = evRemaining(state, s);
      const passed = c.interval_index >= s.departure_interval;
      const verified = r.verified_ev_delivered_by_ev_model_kwh ? r.verified_ev_delivered_by_ev_model_kwh[s.ev_id] : null;
      return html`
        <h3>${s.ev_id}</h3>
        <dl class="facts">
          <dt>Requested</dt><dd>${fmtNum(s.requested_model_kwh, 'kWh (model)')}</dd>
          <dt>Deadline</dt><dd>${fmtTime(intervalTime(c, s.departure_interval))}</dd>
          <dt>Delivered, verified</dt><dd>${fmtNum(verified, 'kWh (model)')}</dd>
          <dt>Still to deliver</dt><dd>${fmtNum(remaining, 'kWh (model)')}</dd>
        </dl>
        ${passed && remaining > 1e-9 ? html`<div class="notice tone-bad"><p><strong>Service shortfall.</strong> The deadline passed with ${fmtNum(remaining, 'kWh (model)')} not delivered.</p></div>` : ''}
        <form data-ev="${s.ev_id}" class="req-form">
          <details>
            <summary>Change this requirement</summary>
            <label class="field">Energy needed (kWh, model) <input type="number" name="kwh" min="0" step="0.5" value="${s.requested_model_kwh}" required></label>
            <label class="field">Deadline (IST, model time)
              <select name="departure">
                ${Array.from({ length: c.horizon_intervals - c.interval_index + 1 }, (_, n) => c.interval_index + n).filter((n) => n > s.arrival_interval).map((n) => html`<option value="${n}" ${n === s.departure_interval ? attr('selected') : ''}>${fmtTime(intervalTime(c, n))}</option>`)}
              </select>
            </label>
            <button type="submit">Request a new proposal</button>
            <p class="muted">Your accepted plan stays in place until you accept the new proposal.</p>
          </details>
        </form>`;
    });
    put('charging', html`
      <h2>Charging</h2>
      ${r.verified_ev_unavailable_reason ? html`<div class="notice tone-unknown"><p><span aria-hidden="true">? </span>Energy per EV cannot be verified: one combined meter cannot be attributed to an EV.</p></div>` : ''}
      ${sessions}
      <p class="muted">This is electricity delivered to the charging circuit, not battery charge level.</p>`);
  }

  function renderAdvisory() {
    const adv = state.active_advisory;
    const a = state.apartment;
    put('advisory', html`
      <h2>Peak advisory</h2>
      ${adv ? html`
        <p class="big">${fmtWindows(adv.peak_windows).join(', ')}</p>
        <p>Avoid running flexible loads in these hours where you can.</p>
        <dl class="facts">
          <dt>Forecast region</dt><dd>${adv.geographic_scope}</dd>
          <dt>Issued</dt><dd>${fmtTime(adv.issued_at)} by the demonstration operator</dd>
          <dt>Forecast data</dt><dd>${fmtSource(adv.source_kind)}</dd>
          <dt>Advisory ID</dt><dd><code>${adv.advisory_id}</code></dd>
        </dl>` : html`<p>No advisory has been issued for this run.</p>`}
      <h3>Allowance for participating loads</h3>
      <p class="big">${fmtNum(a.allowance_model_kw, 'kW (model)')}</p>
      <p class="muted">Covers ${a.allowance_scope || 'participating loads only'}. Set by the operator. It is not a whole-building or transformer limit.</p>`);
  }

  function renderReadings() {
    const o = state.observation;
    const q = fmtQuality(o?.quality);
    put('readings', html`
      <h2>Where the readings come from</h2>
      <p>${chip(q)}</p>
      <p>${q.detail}</p>
      <dl class="facts">
        <dt>Source</dt><dd>${o ? fmtSource(o.source_kind) : 'No reading yet'}</dd>
        <dt>Meters</dt><dd>${fmtScope(o?.measurement_scope)}</dd>
        ${o ? html`
          <dt>Reading covers</dt><dd>${fmtTime(intervalTime(state.clock, o.interval_index))} model time</dd>
          <dt>Arrived in</dt><dd>${o.received_at_interval === null || o.received_at_interval === undefined ? (o.quality === 'STALE' ? 'Not arrived' : 'Not stated') : `${fmtTime(intervalTime(state.clock, o.received_at_interval))} model time`}</dd>
          <dt>Combined power</dt><dd>${fmtNum(o.aggregate_model_kw, 'kW (model)')}</dd>
          <dt>Pump power</dt><dd>${fmtNum(o.pump_model_kw, 'kW (model)')}</dd>
          <dt>Charging power</dt><dd>${fmtNum(o.ev_model_kw, 'kW (model)')}</dd>
          ${o.raw_bench ? html`<dt>Bench reading</dt><dd>Raw values from ${o.raw_bench.device_id}, kept separately from model values</dd>` : ''}
        ` : ''}
        <dt>Utility smart meter</dt><dd>Not connected</dd>
      </dl>
      <p class="muted">A whole-connection consumption figure would not prove the pump or charger ran. Pump power alone does not prove water was delivered.</p>
      ${(state.warnings || []).map((w) => html`<p class="muted">${w}</p>`)}`);
  }

  function render() {
    put('meta', html`Run <code>${state.run_id}</code>, ${state.apartment.apartment_id}, state version ${state.revision}. Model time ${fmtTime(state.clock.model_time_utc)}, interval ${state.clock.interval_index} of ${state.clock.horizon_intervals} (${state.clock.model_dt_minutes} min each).`);
    renderNext();
    renderCommitment();
    renderProposal();
    renderExecution();
    renderTank();
    renderCharging();
    renderAdvisory();
    renderReadings();
    tickExpiry();
  }

  function tickExpiry() {
    document.querySelectorAll('[data-expires]').forEach((el) => {
      const iso = el.dataset.expires;
      const mins = Math.ceil((new Date(iso).getTime() - Date.now()) / 60000);
      el.textContent = `${fmtTime(iso)} (${mins > 0 ? `about ${mins} min left` : 'closing now'})`;
    });
  }

  async function refresh() {
    let next;
    try {
      next = await NW_API.state(runId, apartmentId);
    } catch (e) {
      if (e.status === 401) return;
      if (!state) {
        showSignIn(fmtError(e));
      } else if (e.status === 403 || e.status === 404) {
        toast('bad', fmtError(e));
      } else {
        connectionWarned = true;
        toast('warn', `${fmtError(e)} Showing the last state received at ${lastUpdated?.toLocaleTimeString() || 'an unknown time'}. It may be out of date.`);
      }
      return;
    }
    if (connectionWarned) { connectionWarned = false; toast(); }
    lastUpdated = new Date();
    state = next;

    const open = next.pending_proposals?.[0]?.proposal_id || null;
    const wasAccepted = next.active_commitment?.proposal_id === shownProposal;
    if (shownProposal && open !== shownProposal && !wasAccepted && !refresh.deciding) {
      toast('warn', 'The proposal you were viewing closed: it expired or a newer version replaced it. The screen shows the latest state.');
    }
    shownProposal = open;
    if (open && !deliveredSent.has(open)) {
      deliveredSent.add(open);
      NW_API.delivered(open).catch(() => deliveredSent.delete(open));
    }

    const key = `${next.clock.interval_index}/${next.revision}/${next.execution?.claims?.length || 0}`;
    if (key !== reportKey) {
      reportKey = key;
      // Only the counts and coverage are used here: the report's energy values are simulator truth, which a manager's sensors may not support.
      report = await NW_API.report(runId).catch(() => null);
    }

    $('signin').hidden = true;
    $('loading').hidden = true;
    $('app').hidden = false;

    // Do not redraw under someone's fingers; the next poll catches up.
    const editing = document.activeElement?.closest?.('.req-form') || document.querySelector('.req-form details[open]');
    const json = JSON.stringify([next, report]);
    if (json !== lastJson && !editing) {
      lastJson = json;
      render();
    }
  }

  async function act(button, work, done) {
    button.disabled = true;
    document.querySelectorAll('.req-form details[open]').forEach((d) => { d.open = false; });
    try {
      await work();
      toast('good', done);
    } catch (e) {
      if (e.status !== 401) toast('bad', fmtError(e));
    }
    document.activeElement?.blur?.();
    lastJson = null;
    await refresh();
  }

  document.addEventListener('click', (ev) => {
    const b = ev.target.closest('button[data-act]');
    if (!b) return;
    const p = state.pending_proposals?.[0];
    if (b.dataset.act === 'accept' || b.dataset.act === 'decline') {
      const accept = b.dataset.act === 'accept';
      refresh.deciding = true;
      act(b, () => NW_API.decide(p, p.options[0].option_id, accept ? 'ACCEPT' : 'DECLINE'),
        accept ? 'Plan accepted. Nothing has been switched: the actions are still yours to do.' : 'Proposal declined. Your earlier plan, if any, still applies.')
        .finally(() => { refresh.deciding = false; });
    } else if (b.dataset.act === 'claim') {
      const c = state.active_commitment;
      act(b, () => NW_API.claim(state.run_id, c.commitment_id, state.clock.interval_index, b.dataset.kind),
        'Report recorded. Sensors have not confirmed it.');
    }
  });

  document.addEventListener('submit', (ev) => {
    const form = ev.target.closest('.req-form');
    if (!form) return;
    ev.preventDefault();
    const button = form.querySelector('button');
    const update = { ev_id: form.dataset.ev, requested_model_kwh: Number(form.kwh.value), departure_interval: Number(form.departure.value) };
    form.querySelector('details').open = false;
    refresh.deciding = true;
    act(button, () => NW_API.requirements(state.run_id, [update]), 'New proposal requested. Review it before accepting.')
      .finally(() => { refresh.deciding = false; });
  });

  $('signin-form').addEventListener('submit', async (ev) => {
    ev.preventDefault();
    const button = ev.target.querySelector('button');
    button.disabled = true;
    runId = $('run-id').value.trim();
    apartmentId = $('apartment-id').value.trim();
    try {
      await NW_API.signIn({ apartment_id: apartmentId, access_code: $('access-code').value });
      $('access-code').value = '';
      store.set('nivawatt.manager.run', runId);
      store.set('nivawatt.manager.apartment', apartmentId);
      toast();
      $('signin').hidden = true;
      $('loading').hidden = false;
      await refresh();
    } catch (e) {
      toast('bad', fmtError(e));
    }
    button.disabled = false;
  });

  $('sign-out').addEventListener('click', () => {
    NW_API.signOut();
    state = null;
    lastJson = null;
    put('meta', '');
    showSignIn();
  });

  NW_API.init('manager', (e) => { state = null; lastJson = null; showSignIn(fmtError(e)); });
  if (NW_API.hasSession() && runId) {
    $('loading').hidden = false;
    refresh();
  } else {
    showSignIn();
  }
  setInterval(() => { if (state && !document.hidden) refresh(); }, POLL_MS);
  setInterval(tickExpiry, 15000);
  document.addEventListener('visibilitychange', () => { if (state && !document.hidden) refresh(); });
})();
