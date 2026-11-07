"""Software stand-in for the bench device: produces TELEMETRY_EXAMPLE-shaped readings (source_kind=synthetic).

It models the switches a person operates, tank mass balance and sensor noise, then emits raw readings:
true-scale watts per branch plus model-scale tank litres. It knows nothing about plans, claims or verdicts.
"""
import json
import random
import uuid
from pathlib import Path

from simulation import plant

PROFILES = Path(__file__).resolve().parent / "profiles"


def load_profile(name="apartment_reference"):
    return json.loads((PROFILES / f"{name}.json").read_text())


class DeviceEmulator:
    def __init__(self, profile, run_id, apartment_id="APT_1", device_id="bench-1", seed=0):
        self.pf, self.run_id, self.apartment_id, self.device_id = profile, run_id, apartment_id, device_id
        self.rng = random.Random(seed)
        self.tank_l = float(profile["tank"]["initial_l"])
        self.pump_on = self.ev_on = False
        self.dry = False  # fault: pump runs but source water is absent
        self.ev_requested_kwh = 10.0  # vehicle stops drawing once this model energy is delivered
        self.ev_delivered_kwh = 0.0
        self.boot = 1
        self.boot_prefix = f"boot-{uuid.uuid4().hex[:12]}"  # a real device gets a fresh boot id at every power-up
        self.seq = 0
        self.mono_ms = 0
        self.withdrawal = plant.default_withdrawals()
        em = profile["emulator"]
        self.period_s = em["sample_period_s"]
        self.time_scale = 900 / em["seconds_per_model_interval"]  # model seconds per real second

    def reboot(self):
        """Device restart: new session id, sequence and monotonic clock start again from zero."""
        self.boot += 1
        self.seq = 0
        self.mono_ms = 0

    def sample(self, interval_index):
        """Advance one sample period of physics and return one telemetry payload."""
        pf, dt_model_h = self.pf, self.period_s * self.time_scale / 3600
        per_interval = self.pf["emulator"]["seconds_per_model_interval"] / self.period_s
        if self.pump_on and not self.dry:
            self.tank_l += pf["pump"]["flow_lpm"] * 60 * dt_model_h
        self.tank_l = min(self.tank_l, pf["tank"]["capacity_l"])  # overflow controller
        w = self.withdrawal[interval_index % len(self.withdrawal)] / per_interval
        self.tank_l = max(0.0, self.tank_l - w)
        noise = pf["sensor_noise"]
        pump_w = pf["pump"]["rated_kw"] * 1000 * (1 + self.rng.gauss(0, noise["power_fraction_sd"])) if self.pump_on else 0.0
        ev_w = 0.0
        if self.ev_on and self.ev_delivered_kwh < self.ev_requested_kwh - 1e-9:
            ev_w = pf["ev_charger"]["rated_kw"] * 1000 * (1 + self.rng.gauss(0, noise["power_fraction_sd"]))
            self.ev_delivered_kwh += ev_w / 1000 * dt_model_h
        self.seq += 1
        self.mono_ms += int(self.period_s * 1000)
        return {
            "schema_version": "0.2", "run_id": self.run_id, "apartment_id": self.apartment_id,
            "device_id": self.device_id, "device_session_id": f"{self.boot_prefix}-{self.boot}", "seq_num": self.seq,
            "device_monotonic_ms": self.mono_ms, "source_kind": "synthetic",
            "supply_present": True, "voltage_v": pf["pump"]["supply_v"],
            "aggregate_power_w": round(pump_w + ev_w, 1), "pump_power_w": round(pump_w, 1),
            "ev_load_power_w": round(ev_w, 1),
            "tank_volume_l": round(max(0.0, self.tank_l + self.rng.gauss(0, noise["tank_l_sd"])), 1),
            "sump_water_available": not self.dry,
            "pump_switch_position": "ON" if self.pump_on else "OFF",
            "ev_switch_position": "ON" if self.ev_on else "OFF",
            "branch_attribution": "MEASURED_BRANCHES", "quality": "VALID",
            "profile_id": pf["profile_id"],
            "note": "Emulated device reading (synthetic). Not a physical sensor.",
        }

    def interval_samples(self, interval_index):
        n = int(round(self.pf["emulator"]["seconds_per_model_interval"] / self.period_s))
        return [self.sample(interval_index) for _ in range(n)]
