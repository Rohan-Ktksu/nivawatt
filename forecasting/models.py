"""Day-ahead hourly forecasts of Karnataka state load.

Issue time = forecast_start (00:00 IST of the forecast day D, i.e. 18:30 UTC of D-1).
Availability assumption (unvalidated publication lag): reports for day D-2 and earlier are
available at issue. So every input lag is >= 48 h, and training targets end before D-1.
"""
import numpy as np
import pandas as pd

H = pd.Timedelta(hours=1)
LAGS_H = (48, 168, 336)
MODELS = {"seasonal_naive": "seasonal_naive", "ridge_lag_calendar": "trained_regression"}
AVAILABLE_UNTIL = pd.Timedelta(hours=24)  # data with time < forecast_start - 24h is usable


def target_hours(forecast_start):
    return pd.date_range(forecast_start, periods=24, freq="h")


def seasonal_naive(s, forecast_start):
    return s.reindex(target_hours(forecast_start) - 168 * H).to_numpy()


def features(s, idx):
    cols = [s.reindex(idx - lag * H).to_numpy() for lag in LAGS_H]
    local = idx + pd.Timedelta(hours=5, minutes=30)
    cols += [(local.hour == h).astype(float) for h in range(24)]
    cols += [(local.day_of_week == d).astype(float) for d in range(1, 7)]  # Monday is the base
    return np.column_stack(cols)


class Ridge:
    """Closed-form ridge on standardized lag features (calendar dummies left unscaled)."""

    def __init__(self, alpha):
        self.alpha = alpha

    def fit(self, X, y):
        n = len(LAGS_H)
        self.mu, self.sd = X[:, :n].mean(0), X[:, :n].std(0) + 1e-9
        Z = self._z(X)
        A = Z.T @ Z + self.alpha * np.eye(Z.shape[1])
        A[0, 0] -= self.alpha  # do not penalize intercept
        self.w = np.linalg.solve(A, Z.T @ y)
        return self

    def _z(self, X):
        n = len(LAGS_H)
        X = X.copy()
        X[:, :n] = (X[:, :n] - self.mu) / self.sd
        return np.column_stack([np.ones(len(X)), X])

    def predict(self, X):
        return self._z(X) @ self.w


def training_rows(s, day_starts):
    idx = pd.DatetimeIndex([t for d in day_starts for t in target_hours(d)])
    X, y = features(s, idx), s.reindex(idx).to_numpy()
    ok = ~np.isnan(X).any(1) & ~np.isnan(y)
    return X[ok], y[ok]


def fit_ridge(s, train_days, alpha):
    X, y = training_rows(s, train_days)
    if len(y) < 24 * 14:
        raise ValueError("fewer than 14 usable training days")
    return Ridge(alpha).fit(X, y), len(y) // 24


def top3(pred, forecast_start):
    order = sorted(range(24), key=lambda i: (-pred[i], i))[:3]  # tie -> earliest start
    hours = target_hours(forecast_start)
    return sorted(order), [{"start": iso(hours[i]), "end": iso(hours[i] + H)} for i in sorted(order)]


def iso(ts):
    return pd.Timestamp(ts).strftime("%Y-%m-%dT%H:%M:%SZ")
