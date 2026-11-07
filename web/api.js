// The only place the browser talks to the service. Same origin, /api/v1, bearer demo session.
// Classic script rather than an ES module: some Windows registries serve .js as text/plain,
// which browsers refuse for modules.
const NW_API = (() => {
  class ApiError extends Error {
    constructor(status, code, message, revision) {
      super(message);
      this.status = status;
      this.code = code;
      this.revision = revision;
    }
  }

  let role = null;
  let onSignedOut = () => {};

  // Storage can throw in private windows; the session then lasts until the page reloads.
  let memoryToken = null;
  const key = () => `nivawatt.session.${role}`;
  function token() {
    try { return sessionStorage.getItem(key()) || memoryToken; } catch { return memoryToken; }
  }
  function setToken(value) {
    memoryToken = value;
    try {
      if (value) sessionStorage.setItem(key(), value);
      else sessionStorage.removeItem(key());
    } catch { /* memoryToken already holds it */ }
  }

  // crypto.randomUUID is unavailable on plain http, which is how phones reach the local service.
  const requestId = (prefix) => `${prefix}-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;

  async function call(method, path, body) {
    const headers = {};
    if (body !== undefined) headers['Content-Type'] = 'application/json';
    if (token()) headers.Authorization = `Bearer ${token()}`;
    let res;
    try {
      res = await fetch(`/api/v1${path}`, { method, headers, body: body === undefined ? undefined : JSON.stringify(body) });
    } catch {
      throw new ApiError(0, 'NETWORK', 'Cannot reach the NivaWatt service. Check that it is running and that this device is on the same network.');
    }
    let data = null;
    try { data = await res.json(); } catch { /* non-JSON error page; handled below */ }
    if (res.ok) return data;
    const err = (data && data.error) || {};
    const failure = new ApiError(res.status, err.code || `HTTP_${res.status}`, err.message || `The service returned status ${res.status}.`, data && data.revision);
    if (res.status === 401 && failure.code !== 'INVALID_ACCESS_CODE') {
      setToken(null);
      onSignedOut(failure);
    }
    throw failure;
  }

  const q = encodeURIComponent;

  return {
    ApiError,
    requestId,
    init(r, signedOut) { role = r; onSignedOut = signedOut; },
    hasSession: () => Boolean(token()),
    signOut: () => setToken(null),
    async signIn(credentials) {
      const out = await call('POST', '/demo/session', { role, ...credentials });
      setToken(out.token);
      return out;
    },
    evaluation: () => call('GET', '/forecasts/evaluation'),
    replayForecast: (modelName, forecastStart) => call('POST', '/forecasts/replay', {
      // Same model and start returns the same immutable snapshot.
      request_id: `forecast-${modelName}-${forecastStart}`,
      dataset_id: 'kptcl-load-curve',
      model_name: modelName,
      forecast_start: forecastStart,
    }),
    forecast: (id) => call('GET', `/forecasts/${q(id)}`),
    actuals: (id) => call('GET', `/forecasts/${q(id)}/actuals`),
    createRun: (clockStart, scenario, apartmentParams) => call('POST', '/runs', {
      request_id: requestId('run'),
      clock_start_utc: clockStart,
      scenario,
      ...(apartmentParams ? { apartment_params: apartmentParams } : {}),
    }),
    listRuns: () => call('GET', '/runs'),
    createExperiment: (runId) => call('POST', '/experiments', { request_id: requestId('exp'), ...(runId ? { run_id: runId } : {}) }),
    experiment: (id) => call('GET', `/experiments/${q(id)}`),
    operatorState: (runId) => call('GET', `/operator/state?run_id=${q(runId)}`),
    state: (runId, apartmentId) => call('GET', `/state?run_id=${q(runId)}&apartment_id=${q(apartmentId)}`),
    report: (runId) => call('GET', `/runs/${q(runId)}/report`),
    issueAdvisory: (runId, knownFromInterval, forecast, windows, targets) => call('POST', '/events', {
      request_id: `advisory-${runId}-${forecast.forecast_id}-${windows.map((w) => w.start).join('_')}`,
      kind: 'peak_advisory',
      run_id: runId,
      known_from_interval: knownFromInterval,
      forecast_id: forecast.forecast_id,
      target_apartments: targets,
      peak_windows: windows,
      valid_from: forecast.forecast_start,
      valid_until: forecast.forecast_end,
    }),
    step: (runId, interval, switches, reading) => call('POST', `/runs/${q(runId)}/step`, {
      // Keyed to the interval so a double tap cannot advance the clock twice.
      request_id: `step-${runId}-${interval}-${switches.pump}-${switches.ev}-${reading}`,
      actual_switches: switches,
      ...(reading === 'delayed' ? { delay_observation: true } : {}),
      ...(reading === 'missing' ? { drop_observation: true } : {}),
    }),
    delivered: (proposalId) => call('POST', `/proposals/${q(proposalId)}/delivered`),
    decide: (proposal, optionId, decision) => call('POST', `/proposals/${q(proposal.proposal_id)}/decision`, {
      request_id: `decision-${proposal.proposal_id}-${optionId}-${decision}`,
      run_id: proposal.run_id,
      expected_revision: proposal.revision,
      option_id: optionId,
      decision,
    }),
    claim: (runId, commitmentId, interval, kind) => call('POST', '/execution/claims', {
      request_id: `claim-${commitmentId}-${interval}-${kind}`,
      run_id: runId,
      commitment_id: commitmentId,
      interval_index: interval,
      action_id: `${commitmentId}:${interval}:${kind}`,
    }),
    requirements: (runId, evSessions) => call('POST', '/requirements', {
      request_id: requestId('req'),
      run_id: runId,
      ev_sessions: evSessions,
    }),
  };
})();
