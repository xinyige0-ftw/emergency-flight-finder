"""Phase 3: SMS & WhatsApp alerts via Twilio when route statuses change."""
from __future__ import annotations

import os
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from rich.console import Console

from .models import Route
from .supabase_store import is_configured as _supabase_configured
from .supabase_store import alert_subscriptions_load as _subs_load_sb

console = Console(stderr=True)

ALERT_COOLDOWN_SECONDS = 300  # 5 min between alerts for the same route
STATE_FILE = Path.home() / ".evac_alert_state.json"
SUBSCRIPTIONS_FILE = Path.home() / ".evac_alert_subscriptions.json"


def _load_subscriptions() -> dict:
    """Load persisted alert subscription (file fallback when no Supabase)."""
    if SUBSCRIPTIONS_FILE.exists():
        try:
            return json.loads(SUBSCRIPTIONS_FILE.read_text())
        except Exception:
            pass
    return {}


def _save_subscriptions(data: dict) -> None:
    try:
        SUBSCRIPTIONS_FILE.parent.mkdir(parents=True, exist_ok=True)
        SUBSCRIPTIONS_FILE.write_text(json.dumps(data))
    except Exception:
        pass


def _get_whatsapp_recipients() -> list[str]:
    """Supabase-backed when configured, else file/env."""
    if _supabase_configured():
        phones = _subs_load_sb()
        if phones:
            return phones
    env_phone = (os.environ.get("EVAC_ALERT_WHATSAPP") or "").strip()
    if env_phone:
        return [env_phone]
    file_phone = (_load_subscriptions().get("whatsapp") or "").strip()
    if file_phone:
        return [file_phone]
    return []


WHATSAPP_CONTENT_SID = os.environ.get("WHATSAPP_CONTENT_SID", "HX2238fa5df250b29a9158e67929229e0a")


class AlertConfig:
    def __init__(
        self,
        twilio_sid: str = "",
        twilio_token: str = "",
        twilio_from: str = "",
        twilio_whatsapp_from: str = "",
        phone_to: str = "",
        whatsapp_to: str = "",
        enabled: bool = True,
        cooldown: int = ALERT_COOLDOWN_SECONDS,
        content_sid: str = "",
    ):
        self.twilio_sid = twilio_sid or os.environ.get("TWILIO_ACCOUNT_SID", "")
        self.twilio_token = twilio_token or os.environ.get("TWILIO_AUTH_TOKEN", "")
        self.twilio_from = twilio_from or os.environ.get("TWILIO_FROM_NUMBER", "")
        self.twilio_whatsapp_from = twilio_whatsapp_from or os.environ.get(
            "TWILIO_WHATSAPP_FROM", "whatsapp:+15558376873"
        )
        self.phone_to = phone_to or os.environ.get("EVAC_ALERT_PHONE", "")
        self._whatsapp_to_override = whatsapp_to or ""
        self.enabled = enabled
        self.cooldown = cooldown
        self.content_sid = content_sid or WHATSAPP_CONTENT_SID

    @property
    def whatsapp_recipients(self) -> list[str]:
        """Supabase + file/env; supports multiple subscribers."""
        if self._whatsapp_to_override:
            return [self._whatsapp_to_override]
        return _get_whatsapp_recipients()

    @property
    def whatsapp_to(self) -> str:
        """Single recipient for backward compat; first from list."""
        r = self.whatsapp_recipients
        return r[0] if r else ""

    @property
    def is_configured(self) -> bool:
        if not (self.twilio_sid and self.twilio_token):
            return False
        if not (self.phone_to or self.whatsapp_recipients):
            return False
        if self.phone_to and not self.twilio_from:
            return False
        if self.whatsapp_recipients and not self.twilio_whatsapp_from:
            return False
        return True


def _load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except Exception:
            pass
    return {}


def _save_state(state: dict):
    try:
        STATE_FILE.write_text(json.dumps(state))
    except Exception:
        pass


def detect_changes(current: list[Route], previous: list[Route]) -> list[dict]:
    """Compare two route snapshots and return a list of changes."""
    prev_map = {r.name: r for r in previous}
    changes = []

    for route in current:
        prev = prev_map.get(route.name)
        if not prev:
            changes.append({
                "route": route.name,
                "type": "new_route",
                "message": f"New route available: {route.name}",
            })
            continue

        old_statuses = [l.status.value for l in prev.flight_legs]
        new_statuses = [l.status.value for l in route.flight_legs]

        if old_statuses != new_statuses:
            for i, (old, new) in enumerate(zip(old_statuses, new_statuses)):
                if old != new:
                    fn = route.flight_legs[i].flight_number if i < len(route.flight_legs) else "?"
                    changes.append({
                        "route": route.name,
                        "type": "status_change",
                        "flight": fn,
                        "old": old,
                        "new": new,
                        "message": f"{fn}: {old.upper()} → {new.upper()}",
                    })

        if prev.price_economy_usd and route.price_economy_usd:
            diff = route.price_economy_usd - prev.price_economy_usd
            if abs(diff) > 50:
                direction = "dropped" if diff < 0 else "increased"
                changes.append({
                    "route": route.name,
                    "type": "price_change",
                    "message": f"{route.name}: price {direction} by ${abs(diff):.0f}",
                })

    for prev_route in previous:
        if prev_route.name not in {r.name for r in current}:
            changes.append({
                "route": prev_route.name,
                "type": "route_removed",
                "message": f"Route no longer available: {prev_route.name}",
            })

    return changes


async def send_alerts(changes: list[dict], config: AlertConfig) -> int:
    """Send SMS/WhatsApp alerts for detected changes. Returns count of alerts sent."""
    if not config.is_configured:
        return 0
    if not changes:
        return 0

    state = _load_state()
    now = time.time()
    sent = 0

    priority_types = {"status_change", "new_route", "route_removed"}
    urgent = [c for c in changes if c["type"] in priority_types]
    alerts_to_send = urgent if urgent else changes[:3]

    for change in alerts_to_send:
        key = f"{change['route']}:{change['type']}"
        last_sent = state.get(key, 0)
        if now - last_sent < config.cooldown:
            continue

        body = f"🚨 航班变动提醒: {change['message']}"

        try:
            if config.phone_to:
                await _send_twilio_sms(config, config.phone_to, body)
                sent += 1
            for phone in config.whatsapp_recipients:
                await _send_twilio_whatsapp(config, phone, body)
                sent += 1
            state[key] = now
        except Exception as e:
            console.print(f"[red]Alert send failed: {e}[/red]")

    _save_state(state)
    return sent


async def _send_twilio_sms(config: AlertConfig, to: str, body: str):
    import httpx
    url = f"https://api.twilio.com/2010-04-01/Accounts/{config.twilio_sid}/Messages.json"
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(
            url,
            auth=(config.twilio_sid, config.twilio_token),
            data={"From": config.twilio_from, "To": to, "Body": body},
        )
        if resp.status_code not in (200, 201):
            raise Exception(f"Twilio SMS failed: {resp.status_code} {resp.text[:200]}")
    console.print(f"[green]SMS sent to {to}[/green]")


async def _send_twilio_whatsapp(config: AlertConfig, to: str, body: str):
    """Send WhatsApp via Twilio Content API template (business-initiated, no 24h window)."""
    import json as _json
    import httpx
    url = f"https://api.twilio.com/2010-04-01/Accounts/{config.twilio_sid}/Messages.json"
    wa_from = config.twilio_whatsapp_from
    if not wa_from.startswith("whatsapp:"):
        wa_from = f"whatsapp:{wa_from}"
    wa_to = f"whatsapp:{to}" if not to.startswith("whatsapp:") else to

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    content_vars = _json.dumps({"1": timestamp, "2": "1", "3": body})

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(
            url,
            auth=(config.twilio_sid, config.twilio_token),
            data={
                "From": wa_from,
                "To": wa_to,
                "ContentSid": config.content_sid,
                "ContentVariables": content_vars,
            },
        )
        if resp.status_code not in (200, 201):
            raise Exception(f"Twilio WhatsApp failed: {resp.status_code} {resp.text[:200]}")
    console.print(f"[green]WhatsApp sent to {to}[/green]")


def print_alert_status(config: AlertConfig):
    if config.is_configured:
        targets = []
        if config.phone_to:
            targets.append(f"SMS: {config.phone_to}")
        if config.whatsapp_to:
            targets.append(f"WhatsApp: {config.whatsapp_to}")
        console.print(f"[green]Alerts ON → {', '.join(targets)}[/green]")
    else:
        console.print("[dim]Alerts OFF — set TWILIO_* env vars to enable[/dim]")
