#!/usr/bin/env python3
"""
live.py — Render app ko 24x7 active rakhne ke liye keep-alive pinger.

Chalane ke tarike (koi ek):
 1. Apne PC/laptop par:   BOT_URL=https://your-app.onrender.com python live.py
 2. Kisi bhi free host par (Replit, Termux, etc.)
 3. Best option: UptimeRobot (free) — apne Render URL par har 5 min HTTP monitor banao.
"""
import os
import time

import requests

BASE_URL = (os.environ.get("RENDER_EXTERNAL_URL")
            or os.environ.get("BOT_URL", "http://127.0.0.1:10000")).rstrip("/")
INTERVAL = int(os.environ.get("PING_INTERVAL", "600"))  # 10 min

def ping():
    try:
        r = requests.get(BASE_URL + "/health", timeout=10)
        print(f"[keep-alive] {BASE_URL}/health -> {r.status_code}")
    except Exception as e:
        print(f"[keep-alive] ERROR: {e}")

if __name__ == "__main__":
    print(f"🔁 Keep-alive started -> {BASE_URL} every {INTERVAL}s")
    while True:
        ping()
        time.sleep(INTERVAL)
