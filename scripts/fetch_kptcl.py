"""Download the KPTCL-derived hourly load archive (ODbL) into data/raw/ and verify its fingerprint.

Pinned to source commit ed46df8 so the recorded fingerprint and backtest stay reproducible.
"""
import hashlib
import sys
import urllib.request
from pathlib import Path

COMMIT = "ed46df89db0fb6f82dd79336e41b058b7c594d44"
URL = f"https://raw.githubusercontent.com/Vonter/kptcl-load-curve/{COMMIT}/data/kptcl.parquet"
SHA256 = "61538bc849335f960bac29dae1a33e8d25221cfc0e3284f832fda320555331ff"
OUT = Path(__file__).resolve().parent.parent / "data" / "raw" / "kptcl.parquet"

if __name__ == "__main__":
    OUT.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(URL, headers={"User-Agent": "nivawatt-fetch"})
    data = urllib.request.urlopen(req, timeout=120).read()
    got = hashlib.sha256(data).hexdigest()
    if got != SHA256:
        sys.exit(f"fingerprint mismatch: {got}")
    OUT.write_bytes(data)
    print(f"saved {OUT} ({len(data)} bytes, sha256 {got})")
