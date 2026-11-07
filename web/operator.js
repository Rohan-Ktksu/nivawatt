(() => {
  const { html, fmtTime, fmtClock, fmtWindows, fmtNum, fmtSource, fmtReason, fmtStatus, fmtQuality, fmtScope, fmtAction, fmtError } = NW_UI;
  const $ = (id) => document.getElementById(id);
  const POLL_MS = 5000;
  const SCENARIOS = {
    branch: null,
    aggregate: { observation_scope: 'aggregate' },
    dry: { source_outage_intervals: Array.from({ length: 96 }, (_, i) => i), tank_init_l: 3100 },
  };

  const store = {
    get: (k) => { try { return localStorage.getItem(k); } catch { return null; } },
    set: (k, v) => { try { localStorage.setItem(k, v); } catch { /* the run link still works */ } },
  };
  let runId = new URLSearchParams(location.search).get('run') || store.get('nivawatt.operator.run');
  let forecastId = store.get('nivawatt.operator.forecast');
  let forecast = null;
  let actuals = null;
  let evaluation = null;
  let op = null;
  let apt = null;
  let lastJson = null;
  let connectionWarned = false;

  let toastTimer;
  const toast = (tone, message) => {
    clearTimeout(toastTimer);
    $('toast').innerHTML = message ? String(html`<div class="notice tone-${tone}"><p>${message}</p></div>`) : '';
    if (tone === 'good') toastTimer = setTimeout(() => toast(), 8000);
  };
  const chip = (s) => html`<span class="chip tone-${s.tone}"><span aria-hidden="true">${s.icon}</span>${s.label}</span>`;
  const put = (id, content) => { $(id).innerHTML = String(content); };
  const on = (attr) => html([attr]);

  function showSignIn(message) {
    $('app').hidden = true;
    $('signin').hidden = false;
    if (message) toast('bad', message);
  }

  function renderForecast() {
    if (!forecast) {
      put('forecast', html`<p class="muted" style="margin-top:.75rem">Load a saved forecast to see its source and peak hours.</p>`);
      return;
    }
    const f = forecast;
    const actualBy = Object.fromEntries((actuals?.points || []).map((p) => [p.start, p.actual_mw]));
    const values = f.points.flatMap((p) => [p.predicted_mw, actualBy[p.start] ?? 0]);
    const top = Math.max(...values, 1);
    const peaks = new Set(f.peak_windows.map((w) => w.start));
    const test = evaluation?.test?.[f.model_name];
    const dv = evaluation?.data_validation;
    put('forecast', html`
      <div class="columns wide-left" style="margin-top:1rem">
        <div>
          <h3>Forecast peak hours</h3>
          <p class="big">${fmtWindows(f.peak_windows).join(', ')}</p>
          <div class="axis"><span>${fmtNum(top, f.demand_unit, 0)}</span></div>
          <div class="chart" id="chart" role="img" aria-label="Hourly demand forecast. The table below has the same values.">
            ${f.points.map((p) => {
              const a = actualBy[p.start];
              const tip = `${fmtClock(p.start)} IST: forecast ${fmtNum(p.predicted_mw, f.demand_unit, 0)}${actuals ? `, actual ${fmtNum(a, f.demand_unit, 0)}` : ''}${peaks.has(p.start) ? ', forecast peak hour' : ''}`;
              return html`<button type="button" class="bar ${peaks.has(p.start) ? 'peak' : ''}" data-tip="${tip}" aria-label="${tip}">
                <i style="height:${(p.predicted_mw / top) * 100}%"></i>
                ${a === null || a === undefined ? '' : html`<b style="bottom:${(a / top) * 100}%"></b>`}
              </button>`;
            })}
          </div>
          <div class="axis"><span>${fmtClock(f.forecast_start)} IST</span><span>${fmtClock(f.forecast_end)} IST</span></div>
          <div class="legend">
            <span>Forecast</span><span class="l-peak">Forecast peak hour</span>
            ${actuals ? html`<span class="l-actual">Actual, for evaluation only</span>` : ''}
          </div>
          <p class="readout" id="readout" aria-live="polite">Hover or tap a bar for its values.</p>
          ${actuals ? html`<p>Forecast error on this day: <strong>${fmtNum(actuals.mae_mw, f.demand_unit, 1)}</strong> mean absolute error. Actuals are never given to the scheduler.</p>` : ''}
          <details>
            <summary>Show values as a table</summary>
            <div class="scroll"><table>
              <thead><tr><th>Hour (IST)</th><th class="n">Forecast (${f.demand_unit})</th>${actuals ? html`<th class="n">Actual (${f.demand_unit})</th>` : ''}<th>Peak</th></tr></thead>
              <tbody>${f.points.map((p) => html`<tr><td>${fmtClock(p.start)}</td><td class="n">${fmtNum(p.predicted_mw, '', 1)}</td>${actuals ? html`<td class="n">${fmtNum(actualBy[p.start], '', 1)}</td>` : ''}<td>${peaks.has(p.start) ? 'Yes' : ''}</td></tr>`)}</tbody>
            </table></div>
          </details>
        </div>
        <div>
          <h3>Where this comes from</h3>
          <dl class="facts">
            <dt>Region</dt><dd>${f.geographic_scope}</dd>
            <dt>Source</dt><dd>${f.source_url ? html`<a href="${f.source_url}" rel="noopener">${f.source_name}</a>` : f.source_name}</dd>
            <dt>Kind</dt><dd>${fmtSource(f.source_kind)}</dd>
            <dt>Model</dt><dd>${f.model_name} (${f.model_kind})</dd>
            <dt>Issued</dt><dd>${fmtTime(f.issued_at)}</dd>
            <dt>Covers</dt><dd>${fmtTime(f.forecast_start)} to ${fmtTime(f.forecast_end)}</dd>
            <dt>Last data used</dt><dd>${fmtTime(f.last_observation_time)}</dd>
            <dt>Assumptions</dt><dd>${f.availability_assumptions}</dd>
            <dt>Forecast ID</dt><dd><code>${f.forecast_id}</code></dd>
          </dl>
          ${test ? html`
            <h3>Backtest for this model</h3>
            <p>On ${test.days} held-out days: mean absolute error ${fmtNum(test.mae_mw, 'MW', 1)}, top-3 peak-hour overlap ${fmtNum(test.top3_peak_hour_overlap, '', 3)}. Method: ${evaluation.kind}.</p>` : ''}
          ${dv ? html`
            <div class="notice tone-warn"><p><span aria-hidden="true">! </span><strong>Data quality.</strong> ${fmtNum(dv.missing_hours)} of ${fmtNum(dv.expected_hours)} hours are missing and not filled in. ${fmtNum(dv.duplicate_timestamps_with_differing_values)} duplicate hours had differing values. Publication lag: ${dv.publication_lag}</p></div>` : ''}
        </div>
      </div>`);
  }

  function renderAdvisory() {
    const adv = op?.active_advisory;
    if (adv) {
      put('advisory', html`
        <h2>Peak advisory</h2>
        <p><span class="chip tone-good"><span aria-hidden="true">✓</span>Issued ${fmtTime(adv.issued_at)}</span></p>
        <p class="big">${fmtWindows(adv.peak_windows).join(', ')}</p>
        <dl class="facts">
          <dt>Approved by</dt><dd>${adv.approved_by_demo_operator}</dd>
          <dt>Apartments</dt><dd>${adv.target_apartments.join(', ')}</dd>
          <dt>Valid</dt><dd>${fmtTime(adv.valid_from)} to ${fmtTime(adv.valid_until)}</dd>
          <dt>Forecast ID</dt><dd><code>${adv.forecast_id}</code></dd>
          <dt>Advisory ID</dt><dd><code>${adv.advisory_id}</code></dd>
        </dl>
        <p class="muted">A regional forecast does not set a transformer rating or an apartment limit.</p>`);
      return;
    }
    if (!forecast || !op) {
      put('advisory', html`<h2>Peak advisory</h2><p>${forecast ? 'Start a run to issue an advisory.' : 'Load a forecast and start a run to issue an advisory.'}</p>`);
      return;
    }
    if (document.getElementById('advisory-form')?.dataset.forecast === forecast.forecast_id) return; // keep ticks
    put('advisory', html`
      <h2>Peak advisory</h2>
      <p>No advisory is active. Nothing reaches the apartment until you approve one.</p>
      <form id="advisory-form" data-forecast="${forecast.forecast_id}">
        <fieldset><legend>Peak hours to include</legend>
          ${forecast.peak_windows.map((w) => html`<label class="choice"><input type="checkbox" name="w" value="${w.start}" ${on('checked')}> ${fmtWindows([w])[0]}</label>`)}
        </fieldset>
        <p class="muted">For ${op.apartments.map((a) => a.apartment_id).join(', ')}. The allowance stays at the configured value; it is not worked out from MW.</p>
        <button class="primary" type="submit">Approve and issue advisory</button>
      </form>`);
  }

  function renderApartments() {
    if (!op) {
      put('apartments', html`<h2>Participating apartments</h2><p>Start a run to see apartments.</p>`);
      return;
    }
    const o = apt?.observation;
    const q = fmtQuality(o?.quality);
    const cov = op.observation_coverage;
    const warnings = [];
    if (cov.intervals_elapsed > cov.valid_observations) warnings.push(`${cov.intervals_elapsed - cov.valid_observations} of ${cov.intervals_elapsed} intervals have no usable reading. They are unknown, not zero.`);
    if (o?.quality === 'LATE') warnings.push('The latest reading arrived late, so it is not live.');
    if (apt?.apartment?.pump_state === 'UNKNOWN') warnings.push('Pump state is unknown.');
    if (apt?.readiness?.verified_ev_unavailable_reason) warnings.push('Charging energy per EV cannot be verified from one combined meter.');
    if (apt?.readiness?.water_reserve_status === 'BELOW_MINIMUM') warnings.push('The tank is below its reserve.');
    put('apartments', html`
      <h2>Participating apartments</h2>
      <p class="muted">${op.participating_scope}</p>
      ${op.apartments.map((a) => {
        const s = fmtStatus(a.execution?.observation_status || 'UNOBSERVED');
        return html`
          <h3>${a.apartment_id}</h3>
          <p>${chip(s)}</p>
          ${a.execution?.reason ? html`<p>${fmtReason(a.execution.reason)}</p>` : ''}
          <dl class="facts">
            <dt>Allowance</dt><dd>${fmtNum(a.allowance_model_kw, 'kW (model)')}</dd>
            <dt>Latest participating load</dt><dd>${fmtNum(a.latest_aggregate_model_kw, 'kW (model)')}</dd>
            <dt>Tank</dt><dd>${o && o.tank_l === null ? 'Unknown' : fmtNum(apt?.apartment?.model_tank_l, 'L', 0)}</dd>
            <dt>Accepted plan</dt><dd>${a.active_commitment_id ? html`<code>${a.active_commitment_id}</code>` : 'None'}</dd>
            <dt>Proposals waiting</dt><dd>${fmtNum(a.pending_proposals)}</dd>
            <dt>Manager reports</dt><dd>${a.execution ? `${fmtNum(a.execution.claims?.length)} on this plan. Reports are not measurements` : 'None'}</dd>
          </dl>`;
      })}
      <h3>Measurement evidence</h3>
      <p>${chip(q)}</p>
      <dl class="facts">
        <dt>Source</dt><dd>${o ? fmtSource(o.source_kind) : 'No reading yet'}</dd>
        <dt>Meters</dt><dd>${fmtScope(o?.measurement_scope)}</dd>
        <dt>Usable readings</dt><dd>${fmtNum(cov.valid_observations)} of ${fmtNum(cov.intervals_elapsed)} intervals</dd>
        <dt>Utility smart meter</dt><dd>Not connected</dd>
      </dl>
      ${warnings.map((w) => html`<div class="notice tone-warn"><p><span aria-hidden="true">! </span>${w}</p></div>`)}
      ${op.warnings.map((w) => html`<p class="muted">${w}</p>`)}`);
  }

  async function renderReport() {
    if (!op) { put('report', html`<h2>Run outcome</h2><p>Start a run to see its outcome.</p>`); return; }
    let m;
    try { m = await NW_API.report(runId); } catch (e) {
      put('report', html`<h2>Run outcome</h2><p>The report is not available: ${fmtError(e)}</p>`);
      return;
    }
    const ev = Object.keys(m.ev_delivered_model_kwh || {});
    put('report', html`
      <h2>Run outcome</h2>
      <div class="notice tone-unknown"><p>${fmtSource(m.provenance?.source_kind)}. Worked out by the service from simulator truth, for evaluation. Sensors may not have seen all of this.</p></div>
      <dl class="facts">
        <dt>Intervals run</dt><dd>${fmtNum(m.intervals_simulated)} (${m.model_dt_minutes} min each)</dd>
        <dt>Highest participating load</dt><dd>${fmtNum(m.peak_participating_model_kw, 'kW (model)')}</dd>
        <dt>Over allowance</dt><dd>${fmtNum(m.allowance_exceedance_model_kwh, 'kWh (model)')}</dd>
        <dt>Energy in peak hours</dt><dd>${fmtNum(m.peak_window_energy_model_kwh, 'kWh (model)')}</dd>
        <dt>Total energy</dt><dd>${fmtNum(m.total_participating_energy_model_kwh, 'kWh (model)')}</dd>
        <dt>Below tank reserve</dt><dd>${fmtNum(m.reserve_violation_intervals)} intervals</dd>
        <dt>Unmet water</dt><dd>${fmtNum(m.unmet_withdrawal_l, 'L', 0)}</dd>
        <dt>Final tank</dt><dd>${fmtNum(m.final_tank_l, 'L', 0)}</dd>
        <dt>Pump starts</dt><dd>${fmtNum(m.pump_starts)}</dd>
        ${ev.map((id) => html`
          <dt>${id} delivered</dt><dd>${fmtNum(m.ev_delivered_model_kwh[id], 'kWh (model)')}</dd>
          <dt>${id} shortfall at deadline</dt><dd>${m.ev_shortfall_at_departure_model_kwh?.[id] === null ? 'Deadline not reached' : fmtNum(m.ev_shortfall_at_departure_model_kwh?.[id], 'kWh (model)')}</dd>`)}
        <dt>Reports / contradicted</dt><dd>${fmtNum(m.counts?.claims)} / ${fmtNum(m.counts?.claims_contradicted)}</dd>
        <dt>Deviations seen by sensors</dt><dd>${fmtNum(m.counts?.observed_deviations)}</dd>
        <dt>Proposals / acceptances</dt><dd>${fmtNum(m.counts?.proposals)} / ${fmtNum(m.counts?.acceptances)}</dd>
      </dl>
      <details><summary>How each value is defined</summary>
        <dl class="facts">${Object.entries(m.definitions || {}).map(([k, v]) => html`<dt>${k}</dt><dd>${v}</dd>`)}</dl>
      </details>`);
  }

  function renderSim() {
    $('sim').hidden = !op;
    if (!op) { put('run-link', ''); return; }
    const url = `${location.origin}/manager?run=${encodeURIComponent(runId)}`;
    put('run-link', html`<p style="margin-top:.75rem">Current run <code>${runId}</code></p><p>Manager link: <a href="${url}" id="manager-link">${url}</a></p>`);
    const ex = op.apartments[0]?.execution;
    const ended = op.clock.interval_index >= op.clock.horizon_intervals;
    put('due', html`
      <p><strong>Model time ${fmtTime(op.clock.model_time_utc)}</strong>, interval ${op.clock.interval_index} of ${op.clock.horizon_intervals}.</p>
      <p>Accepted plan for this interval: ${ex?.next_action ? fmtAction(ex.next_action) : 'none'}.</p>`);
    $('step').disabled = ended;
    $('match-plan').disabled = !ex?.next_action;
  }

  function renderMeta() {
    put('meta', op
      ? html`Run <code>${runId}</code>, state version ${op.revision}. Model time ${fmtTime(op.clock.model_time_utc)}.`
      : html`No run selected.`);
  }

  async function refresh() {
    if (runId) {
      try {
        const nextOp = await NW_API.operatorState(runId);
        const nextApt = await NW_API.state(runId, nextOp.apartments[0].apartment_id);
        const json = JSON.stringify([nextOp, nextApt]);
        op = nextOp;
        apt = nextApt;
        if (json !== lastJson) {
          lastJson = json;
          renderMeta();
          renderAdvisory();
          renderApartments();
          renderSim();
          await renderReport();
        }
        if (connectionWarned) { connectionWarned = false; toast(); }
      } catch (e) {
        if (e.status === 401) return;
        if (e.status === 404) {
          runId = null;
          op = null;
          apt = null;
          store.set('nivawatt.operator.run', '');
          toast('warn', 'The saved run no longer exists. Start a new run.');
          renderAll();
        } else {
          connectionWarned = true;
          toast('warn', `${fmtError(e)} Values on screen may be out of date.`);
        }
      }
    }
  }

  function renderAll() {
    renderMeta();
    renderForecast();
    renderAdvisory();
    renderApartments();
    renderSim();
    renderReport();
  }

  async function loadForecast(snapshot) {
    forecast = snapshot;
    forecastId = snapshot.forecast_id;
    store.set('nivawatt.operator.forecast', forecastId);
    actuals = await NW_API.actuals(forecastId).catch(() => null);
    $('forecast-start').value = snapshot.forecast_start;
    renderForecast();
    renderAdvisory();
  }

  async function enter() {
    $('signin').hidden = true;
    $('app').hidden = false;
    evaluation = await NW_API.evaluation().catch(() => null);
    if (evaluation?.demo_forecast_start && !$('forecast-start').value) $('forecast-start').value = evaluation.demo_forecast_start;
    if (!NW_API.hasSession()) return;
    if (forecastId) {
      try { await loadForecast(await NW_API.forecast(forecastId)); } catch { forecastId = null; }
    }
    renderAll();
    await refresh();
  }

  async function busy(button, work) {
    button.disabled = true;
    try {
      await work();
    } catch (e) {
      if (e.status !== 401) toast('bad', fmtError(e));
    }
    button.disabled = false;
    lastJson = null;
    await refresh();
  }

  $('forecast-form').addEventListener('submit', (ev) => {
    ev.preventDefault();
    busy(ev.target.querySelector('button'), async () => {
      await loadForecast(await NW_API.replayForecast($('model').value, $('forecast-start').value.trim()));
      toast('good', 'Saved forecast loaded. It is not issued until you approve an advisory.');
    });
  });

  $('create-run').addEventListener('click', (ev) => {
    if (!forecast) { toast('warn', 'Load a forecast first, so the run starts on the forecast day.'); return; }
    busy(ev.target, async () => {
      const scenario = $('scenario').value;
      const made = await NW_API.createRun(forecast.forecast_start, scenario, SCENARIOS[scenario]);
      runId = made.run_id;
      store.set('nivawatt.operator.run', runId);
      history.replaceState(null, '', `?run=${encodeURIComponent(runId)}`);
      $('step-result').innerHTML = '';
      put('advisory', '');
      toast('good', 'Run started. Approve an advisory, then share the manager link.');
    });
  });

  document.addEventListener('submit', (ev) => {
    if (ev.target.id !== 'advisory-form') return;
    ev.preventDefault();
    const picked = new Set([...ev.target.querySelectorAll('input[name=w]:checked')].map((x) => x.value));
    const windows = forecast.peak_windows.filter((w) => picked.has(w.start));
    if (!windows.length) { toast('warn', 'Pick at least one peak hour to issue an advisory.'); return; }
    busy(ev.target.querySelector('button'), async () => {
      await NW_API.issueAdvisory(runId, op.clock.interval_index, forecast, windows, op.apartments.map((a) => a.apartment_id));
      toast('good', 'Advisory issued. The apartment now has a proposal to review.');
    });
  });

  const radio = (name) => document.querySelector(`input[name=${name}]:checked`).value;
  const setRadio = (name, value) => { document.querySelector(`input[name=${name}][value=${value}]`).checked = true; };

  $('match-plan').addEventListener('click', () => {
    const a = op.apartments[0]?.execution?.next_action;
    if (!a) return;
    setRadio('pump', a.pump === 'ON' ? 'ON' : 'OFF');
    setRadio('ev', a.ev && a.ev !== 'OFF' ? 'ON' : 'OFF');
  });

  $('step').addEventListener('click', (ev) => {
    busy(ev.target, async () => {
      const reading = radio('reading');
      const out = await NW_API.step(runId, op.clock.interval_index, { pump: radio('pump'), ev: radio('ev') }, reading);
      setRadio('reading', 'normal');
      const verdict = (v, label) => (v ? html`<p>${label}: ${chip(fmtStatus(v.observation_status))} ${fmtReason(v.reason)}</p>` : '');
      put('step-result', html`
        <h3 style="margin-top:.75rem">Interval ${out.stepped_interval} checked</h3>
        ${verdict(out.execution, 'This interval')}
        ${verdict(out.late_execution, `Interval ${out.late_execution?.interval_index}, from a late reading`)}
        ${!out.execution && !out.late_execution ? html`<p>No accepted plan covered this interval, so there was nothing to check.</p>` : ''}
        ${out.state?.pending_proposals?.length ? html`<p>A proposal is waiting for the manager.</p>` : ''}`);
    });
  });

  const tip = (ev) => {
    const bar = ev.target.closest?.('.bar');
    if (bar) $('readout').textContent = bar.dataset.tip;
  };
  document.addEventListener('mouseover', tip);
  document.addEventListener('focusin', tip);
  document.addEventListener('click', tip);

  $('signin-form').addEventListener('submit', async (ev) => {
    ev.preventDefault();
    const button = ev.target.querySelector('button');
    button.disabled = true;
    try {
      await NW_API.signIn({ access_code: $('access-code').value });
      $('access-code').value = '';
      toast();
      await enter();
    } catch (e) {
      toast('bad', fmtError(e));
    }
    button.disabled = false;
  });

  $('sign-out').addEventListener('click', () => {
    NW_API.signOut();
    lastJson = null;
    op = null;
    showSignIn();
  });

  NW_API.init('operator', (e) => { lastJson = null; showSignIn(fmtError(e)); });
  if (NW_API.hasSession()) enter(); else showSignIn();
  setInterval(() => { if (NW_API.hasSession() && !document.hidden && !$('app').hidden) refresh(); }, POLL_MS);
})();
