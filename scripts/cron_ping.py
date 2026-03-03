#!/usr/bin/env python3
"""Cron script: ping /api/routes?live=true to trigger change detection + WhatsApp alerts."""
import os
import urllib.request

url = (os.environ.get("CRON_SERVICE_URL") or "").rstrip("/")
if not url:
    exit(0)
try:
    urllib.request.urlopen(f"{url}/api/routes?live=true", timeout=120)
except Exception:
    pass
