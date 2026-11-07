"""Start the NivaWatt local service: python app.py [--port 8780] [--host 127.0.0.1]"""
import argparse

import uvicorn

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1", help="use 0.0.0.0 to reach it from a phone on the LAN")
    ap.add_argument("--port", type=int, default=8780)
    a = ap.parse_args()
    from backend.main import codes
    codes()  # create ignored config/local.json with demo access codes on first start
    uvicorn.run("backend.main:app", host=a.host, port=a.port)
