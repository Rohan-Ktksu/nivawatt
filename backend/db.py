import json
import os
import sqlite3
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOCK = threading.RLock()  # one writer at a time: makes accept/claim/step atomic

SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions(token TEXT PRIMARY KEY, role TEXT, apartment_id TEXT, device_id TEXT, created_at TEXT);
CREATE TABLE IF NOT EXISTS idempotency(request_id TEXT PRIMARY KEY, scope TEXT, body_hash TEXT, status INT, response TEXT);
CREATE TABLE IF NOT EXISTS forecasts(forecast_id TEXT PRIMARY KEY, body TEXT, created_at TEXT);
CREATE TABLE IF NOT EXISTS runs(run_id TEXT PRIMARY KEY, params TEXT, truth TEXT, interval_index INT, revision INT,
  clock_start_utc TEXT, active_advisory_id TEXT, created_at TEXT);
CREATE TABLE IF NOT EXISTS events(event_id TEXT PRIMARY KEY, run_id TEXT, kind TEXT, known_from_interval INT,
  applied INT, body TEXT, created_at TEXT);
CREATE TABLE IF NOT EXISTS proposals(proposal_id TEXT PRIMARY KEY, run_id TEXT, apartment_id TEXT, revision INT,
  status TEXT, reason TEXT, created_at TEXT, expires_at TEXT, body TEXT);
CREATE TABLE IF NOT EXISTS commitments(commitment_id TEXT PRIMARY KEY, run_id TEXT, apartment_id TEXT, proposal_id TEXT,
  option_id TEXT, status TEXT, effective_from_interval INT, ended_at_interval INT, accepted_at TEXT, body TEXT);
CREATE TABLE IF NOT EXISTS claims(claim_id TEXT PRIMARY KEY, run_id TEXT, commitment_id TEXT, interval_index INT,
  action_id TEXT, claimed_at TEXT);
CREATE TABLE IF NOT EXISTS observations(run_id TEXT, interval_index INT, body TEXT, PRIMARY KEY(run_id, interval_index));
CREATE TABLE IF NOT EXISTS executions(run_id TEXT, commitment_id TEXT, interval_index INT, observation_status TEXT,
  reason TEXT, PRIMARY KEY(run_id, commitment_id, interval_index));
CREATE TABLE IF NOT EXISTS truth_log(run_id TEXT, interval_index INT, body TEXT, PRIMARY KEY(run_id, interval_index));
CREATE TABLE IF NOT EXISTS telemetry(id INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT, device_id TEXT,
  device_session_id TEXT, seq_num INT, received_at TEXT, status TEXT, body TEXT);
CREATE TABLE IF NOT EXISTS experiments(experiment_id TEXT PRIMARY KEY, body TEXT, created_at TEXT);
"""

_conn = None


def conn():
    global _conn
    if _conn is None:
        path = os.environ.get("NIVAWATT_DB", str(ROOT / "runtime" / "nivawatt.db"))
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        _conn = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
        _conn.row_factory = sqlite3.Row
        _conn.execute("PRAGMA journal_mode=WAL")
        _conn.executescript(SCHEMA)
    return _conn


def reset():
    """Tests only: drop the cached connection so NIVAWATT_DB can change."""
    global _conn
    if _conn:
        _conn.close()
    _conn = None


def q(sql, *args):
    return conn().execute(sql, args).fetchall()


def one(sql, *args):
    return conn().execute(sql, args).fetchone()


def ex(sql, *args):
    conn().execute(sql, args)


def dumps(o):
    return json.dumps(o, separators=(",", ":"))
