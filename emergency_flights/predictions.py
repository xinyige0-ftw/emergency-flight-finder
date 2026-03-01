"""Phase 6: Smart predictions — historical patterns, wait-vs-go, transit visa checker."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from rich.console import Console

from .models import FlightStatus, ReliabilityScore, Route, Scenario

console = Console(stderr=True)

HISTORY_FILE = Path.home() / ".evac_history.json"

CONFLICT_PATTERNS = {
    "gulf_war_1991": {
        "duration_days": 42,
        "airspace_recovery_days": 3,
        "flight_resume_pattern": "hub_first",
        "notes": "Major carriers resumed within 3 days of ceasefire",
    },
    "iraq_2003": {
        "duration_days": 21,
        "airspace_recovery_days": 7,
        "flight_resume_pattern": "gradual",
        "notes": "Regional airspace reopened in stages over a week",
    },
    "yemen_2015": {
        "duration_days": 365,
        "airspace_recovery_days": None,
        "flight_resume_pattern": "partial",
        "notes": "Some routes never fully resumed. Hub airports stayed open",
    },
    "qatar_blockade_2017": {
        "duration_days": 1279,
        "airspace_recovery_days": 1,
        "flight_resume_pattern": "immediate",
        "notes": "Once resolved, airspace reopened within 24 hours",
    },
    "ukraine_2022": {
        "duration_days": None,
        "airspace_recovery_days": None,
        "flight_resume_pattern": "none",
        "notes": "Ukrainian and Russian airspace remain closed to most carriers",
    },
    "iran_israel_2024": {
        "duration_days": 2,
        "airspace_recovery_days": 1,
        "flight_resume_pattern": "immediate",
        "notes": "Brief closure, flights resumed next day after de-escalation",
    },
}

# Transit visa requirements by passport
TRANSIT_VISA_RULES = {
    "CN": {
        "IST": {"required": False, "notes": "China passport: visa-free transit up to 30 days in Turkey"},
        "LHR": {"required": True, "notes": "China passport: UK transit visa required (DATV or visitor visa)"},
        "ADD": {"required": True, "notes": "China passport: Ethiopia e-visa available on arrival"},
        "DOH": {"required": False, "notes": "China passport: Qatar visa-free for 30 days"},
        "DXB": {"required": False, "notes": "China passport: UAE visa-free for 30 days"},
        "BKK": {"required": False, "notes": "China passport: Thailand visa-free for 30 days"},
        "SIN": {"required": False, "notes": "China passport: Singapore visa-free transit 96h"},
        "KUL": {"required": False, "notes": "China passport: Malaysia visa-free for 30 days"},
        "DEL": {"required": True, "notes": "China passport: India e-visa required"},
        "NRT": {"required": True, "notes": "China passport: Japan transit visa may be required"},
        "ICN": {"required": False, "notes": "China passport: Korea transit without visa up to 72h"},
    },
}


def record_status_snapshot(routes: list[Route]):
    """Save current route statuses to history file for pattern detection."""
    history = _load_history()
    now = datetime.now(timezone.utc).isoformat()

    snapshot = {
        "timestamp": now,
        "routes": [
            {
                "name": r.name,
                "reliability": r.reliability.value,
                "statuses": [l.status.value for l in r.flight_legs],
                "score": r.score,
            }
            for r in routes
        ],
    }

    history.setdefault("snapshots", []).append(snapshot)

    if len(history["snapshots"]) > 500:
        history["snapshots"] = history["snapshots"][-500:]

    _save_history(history)


def analyze_patterns(routes: list[Route]) -> list[dict]:
    """Analyze historical snapshots to detect trends."""
    history = _load_history()
    snapshots = history.get("snapshots", [])

    if len(snapshots) < 3:
        return [{"type": "info", "message": "Need more data points for trend analysis (min 3 snapshots)"}]

    insights = []
    route_names = {r.name for r in routes}

    for name in route_names:
        statuses_over_time = []
        for snap in snapshots[-20:]:
            for r in snap["routes"]:
                if r["name"] == name:
                    statuses_over_time.append({
                        "time": snap["timestamp"],
                        "statuses": r["statuses"],
                        "reliability": r["reliability"],
                    })

        if len(statuses_over_time) >= 3:
            recent = statuses_over_time[-3:]
            if all(s["reliability"] == "low" for s in recent):
                insights.append({
                    "type": "trend_down",
                    "route": name,
                    "message": f"{name}: consistently cancelled — unlikely to resume soon",
                    "confidence": "medium",
                })
            elif recent[-1]["reliability"] == "high" and recent[0]["reliability"] == "low":
                insights.append({
                    "type": "trend_up",
                    "route": name,
                    "message": f"{name}: recovering — was cancelled, now operating",
                    "confidence": "high",
                })
            elif all(s["reliability"] == "high" for s in recent):
                insights.append({
                    "type": "stable",
                    "route": name,
                    "message": f"{name}: stable and reliable over last {len(recent)} checks",
                    "confidence": "high",
                })

    return insights


def wait_vs_go_recommendation(routes: list[Route], scenario: Scenario) -> dict:
    """Recommend whether to go now or wait for better options."""
    viable = [r for r in routes if r.reliability != ReliabilityScore.LOW]

    if not viable:
        return {
            "action": "wait",
            "confidence": "low",
            "reason": "No confirmed operating flights. Wait for status updates.",
            "check_again_hours": 2,
        }

    best = viable[0]
    high_rel = [r for r in viable if r.reliability == ReliabilityScore.HIGH]

    if high_rel and high_rel[0].score < 25:
        return {
            "action": "go_now",
            "confidence": "high",
            "reason": f"Confirmed operating route: {high_rel[0].name} "
                      f"(~{high_rel[0].total_hours:.0f}h, score {high_rel[0].score:.0f})",
            "recommended_route": high_rel[0].name,
        }

    if best.total_hours < 24 and best.reliability == ReliabilityScore.MEDIUM:
        return {
            "action": "go_now",
            "confidence": "medium",
            "reason": f"Best option: {best.name} (~{best.total_hours:.0f}h). "
                      "Status unconfirmed — call airline before leaving.",
            "recommended_route": best.name,
        }

    has_improving = any(
        r.reliability == ReliabilityScore.MEDIUM and r.total_hours < 30
        for r in viable
    )
    if has_improving and best.total_hours > 48:
        return {
            "action": "wait_short",
            "confidence": "medium",
            "reason": "Better options may become available within 24h. "
                      "Current best is 48h+ away. Monitor and decide.",
            "check_again_hours": 4,
        }

    return {
        "action": "go_now",
        "confidence": "medium",
        "reason": f"Take {best.name} (~{best.total_hours:.0f}h). "
                  "Waiting risks options getting worse.",
        "recommended_route": best.name,
    }


def check_transit_visa(passport: str, hub_code: str) -> dict:
    """Check if a transit visa is required for the given passport + hub."""
    passport = passport.upper()
    hub_code = hub_code.upper()

    rules = TRANSIT_VISA_RULES.get(passport, {})
    rule = rules.get(hub_code)

    if rule:
        return {
            "passport": passport,
            "hub": hub_code,
            "visa_required": rule["required"],
            "notes": rule["notes"],
        }

    return {
        "passport": passport,
        "hub": hub_code,
        "visa_required": None,
        "notes": f"Transit visa rules unknown for {passport} passport at {hub_code}. Check manually.",
    }


def check_all_transit_visas(passport: str, routes: list[Route]) -> list[dict]:
    """Check transit visas for all hubs used in all routes."""
    checked_hubs = set()
    results = []

    for route in routes:
        for leg in route.flight_legs[:-1]:
            hub = leg.destination
            if hub not in checked_hubs:
                checked_hubs.add(hub)
                results.append(check_transit_visa(passport, hub))

    return results


def get_historical_context() -> list[dict]:
    """Return historical conflict pattern data for reference."""
    return [
        {"conflict": k, **v}
        for k, v in CONFLICT_PATTERNS.items()
    ]


def _load_history() -> dict:
    if HISTORY_FILE.exists():
        try:
            return json.loads(HISTORY_FILE.read_text())
        except Exception:
            pass
    return {}


def _save_history(data: dict):
    try:
        HISTORY_FILE.write_text(json.dumps(data, indent=2))
    except Exception:
        pass
