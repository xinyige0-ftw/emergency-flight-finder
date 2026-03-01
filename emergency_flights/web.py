"""FastAPI web server — mobile-first UI for Emergency Flight Finder."""
from __future__ import annotations

import os
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Load .env from project root so TWILIO_* and EVAC_ALERT_* are set when running locally
try:
    from dotenv import load_dotenv
    _root = Path(__file__).resolve().parent.parent
    load_dotenv(_root / ".env")
except ImportError:
    pass

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse

from .alerts import AlertConfig, detect_changes, send_alerts, _send_twilio_whatsapp, _send_twilio_sms, _save_subscriptions
from .crowdsource import fetch_all_crowdsource
from .community import (
    CommunityReport, RideShare, get_reports, get_rideshares, get_translations,
    list_scenarios_available, post_rideshare, submit_report, upvote_report,
)
from .config import load_scenario
from .intel import fetch_conflict_news, detect_airspace_changes_from_news, fetch_notams
from .models import AST, Route
from .predictions import (
    analyze_patterns, check_all_transit_visas, get_historical_context,
    record_status_snapshot, wait_vs_go_recommendation,
)
from .pricing import check_prices_and_seats, filter_by_budget, check_multi_passenger_availability
from .routes import build_routes
from .searcher import check_all_flights

app = FastAPI(title="Emergency Flight Finder")

SCENARIOS_DIR = Path(__file__).parent.parent / "scenarios"
STATIC_DIR = Path(__file__).parent.parent / "static"

_previous_routes: list[Route] = []

# Rate limit: 10 POSTs per minute per IP
_rate_limit: dict[str, list[float]] = defaultdict(list)
RATE_LIMIT_WINDOW = 60.0
RATE_LIMIT_MAX = 10


def _rate_limit_check(ip: str) -> bool:
    now = time.time()
    _rate_limit[ip] = [t for t in _rate_limit[ip] if now - t < RATE_LIMIT_WINDOW]
    if len(_rate_limit[ip]) >= RATE_LIMIT_MAX:
        return False
    _rate_limit[ip].append(now)
    return True


def _client_ip(request: Request) -> str:
    return (request.headers.get("x-forwarded-for") or request.client.host or "unknown").split(",")[0].strip()


@app.get("/", response_class=HTMLResponse)
async def index():
    html_path = STATIC_DIR / "index.html"
    return HTMLResponse(html_path.read_text())


@app.get("/sw.js")
async def service_worker():
    sw_path = STATIC_DIR / "sw.js"
    return HTMLResponse(sw_path.read_text(), media_type="application/javascript")


@app.get("/manifest.json")
async def manifest():
    return JSONResponse({
        "name": "Emergency Flight Finder",
        "short_name": "EvacFlight",
        "start_url": "/",
        "display": "standalone",
        "background_color": "#1a1a2e",
        "theme_color": "#e94560",
        "icons": [{"src": "/icon.svg", "sizes": "any", "type": "image/svg+xml"}],
    })


@app.get("/icon.svg")
async def icon():
    svg = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
    <rect width="100" height="100" rx="20" fill="#e94560"/>
    <text x="50" y="65" text-anchor="middle" fill="white" font-size="50" font-family="Arial">E</text>
    </svg>'''
    return HTMLResponse(content=svg, media_type="image/svg+xml")


@app.get("/api/routes")
async def get_routes(
    scenario: str = "bahrain_to_china",
    live: bool = False,
    speed: str = "balanced",
    budget: float = 10000,
    passengers: int = 1,
    passport: str = "CN",
    risk: str = "moderate",
    sort_by: str = "score",
    max_stops: int = 2,
    max_wait: float = 72,
    show_cancelled: bool = True,
):
    global _previous_routes
    now = datetime.now(timezone.utc)

    path = SCENARIOS_DIR / f"{scenario}.yaml"
    if not path.exists():
        return JSONResponse({"error": f"Scenario '{scenario}' not found"}, status_code=404)

    sc = load_scenario(path)
    sc.user.passengers = passengers
    sc.user.passport = passport
    sc.user.budget_usd = budget
    sc.user.risk_tolerance = risk

    if live:
        try:
            sc.known_flights = await check_all_flights(sc.known_flights, live=True)
            sc.known_flights = await check_prices_and_seats(
                sc.known_flights, passengers=passengers, live=True,
            )
            sc.known_flights = filter_by_budget(sc.known_flights, budget, passengers)
            sc.known_flights = check_multi_passenger_availability(sc.known_flights, passengers)
        except Exception:
            pass

    routes = build_routes(sc, now=now, previous_routes=_previous_routes or None,
                          speed_mode=speed, max_stops=max_stops, max_wait_hours=max_wait)

    if not show_cancelled:
        routes = [r for r in routes if r.reliability.value != "low"]

    if sort_by == "depart":
        routes.sort(key=lambda r: r.next_departure or datetime.max.replace(tzinfo=timezone.utc))
    elif sort_by == "price":
        routes.sort(key=lambda r: r.price_economy_usd or 99999)
    elif sort_by == "duration":
        routes.sort(key=lambda r: r.flight_hours)

    alert_config = AlertConfig()
    changes = []
    if _previous_routes and alert_config.is_configured:
        changes = detect_changes(routes, _previous_routes)
        if changes:
            await send_alerts(changes, alert_config)

    record_status_snapshot(routes)
    recommendation = wait_vs_go_recommendation(routes, sc)
    visa_checks = check_all_transit_visas(passport, routes)
    patterns = analyze_patterns(routes)

    _previous_routes = routes

    result = {
        "updated": now.isoformat(),
        "updated_ast": now.astimezone(AST).strftime("%a %b %d, %H:%M AST"),
        "scenario": sc.name,
        "airspace": {
            "closed": sc.airspace_closed,
            "open": sc.airspace_open,
            "restricted": sc.airspace_restricted,
        },
        "escape_routes": [
            {"from": r.origin, "to": r.destination, "via": r.via,
             "hours": r.estimated_hours, "status": r.status}
            for r in sc.escape_routes
        ],
        "routes": [_route_to_dict(r, now) for r in routes],
        "recommendation": recommendation,
        "visa_checks": visa_checks,
        "patterns": patterns,
    }
    return JSONResponse(result)


@app.get("/api/history")
async def get_history():
    return JSONResponse({"conflicts": get_historical_context()})


@app.get("/api/crowdsource")
async def get_crowdsource():
    """External crowdsource: X (Nitter RSS), Telegram RSS, embassy advisories."""
    try:
        data = await fetch_all_crowdsource(max_per_source=15)
    except Exception:
        data = {"x": [], "telegram": [], "embassy": []}
    return JSONResponse(data)


@app.get("/api/news")
async def get_news(scenario: str = "bahrain_to_china"):
    path = SCENARIOS_DIR / f"{scenario}.yaml"
    sc = load_scenario(path) if path.exists() else None

    try:
        news = await fetch_conflict_news(max_items=20)
    except Exception:
        news = []

    airspace_alerts = []
    if sc and news:
        airspace_alerts = detect_airspace_changes_from_news(news, sc)

    return JSONResponse({
        "news": [n.to_dict() for n in news],
        "airspace_alerts": airspace_alerts,
    })


@app.get("/api/notams")
async def get_notams(airports: str = "RUH,JED,DMM,IST"):
    codes = [c.strip().upper() for c in airports.split(",") if c.strip()]
    try:
        notams = await fetch_notams(codes)
    except Exception:
        notams = []
    return JSONResponse({"notams": notams})


@app.get("/api/scenarios")
async def list_scenarios():
    return JSONResponse({"scenarios": list_scenarios_available(SCENARIOS_DIR)})


@app.get("/api/reports")
async def api_get_reports(airport: str = "", flight: str = "", hours: float = 24):
    reports = get_reports(airport=airport, flight=flight, max_age_hours=hours)
    return JSONResponse({"reports": [r.to_dict() for r in reports]})


@app.post("/api/reports")
async def api_submit_report(request: Request,
    report_type: str = "flight_status",
    flight: str = "",
    airport: str = "",
    message: str = "",
    status: str = "",
    reporter: str = "anonymous",
):
    ip = _client_ip(request)
    if not _rate_limit_check(ip):
        return JSONResponse({"ok": False, "error": "Too many requests"}, status_code=429)
    report_type = (report_type or "flight_status")[:50]
    flight = (flight or "")[:20]
    airport = (airport or "")[:20]
    message = (message or "")[:2000]
    status = (status or "")[:30]
    reporter = (reporter or "anonymous")[:100]
    report = CommunityReport(
        reporter=reporter, report_type=report_type,
        flight_number=flight, airport=airport,
        message=message, status=status,
    )
    submit_report(report)
    return JSONResponse({"ok": True, "report": report.to_dict()})


@app.post("/api/reports/{report_id}/upvote")
async def api_upvote(request: Request, report_id: str):
    if not _rate_limit_check(_client_ip(request)):
        return JSONResponse({"ok": False, "error": "Too many requests"}, status_code=429)
    report_id = (report_id or "")[:50]
    ok = upvote_report(report_id)
    return JSONResponse({"ok": ok})


@app.get("/api/rideshares")
async def api_get_rides(origin: str = "", destination: str = ""):
    rides = get_rideshares(origin=origin, destination=destination)
    return JSONResponse({"rides": [r.to_dict() for r in rides]})


@app.post("/api/rideshares")
async def api_post_ride(request: Request,
    origin: str = "",
    destination: str = "",
    departure_time: str = "",
    seats: int = 1,
    contact: str = "",
    notes: str = "",
):
    ip = _client_ip(request)
    if not _rate_limit_check(ip):
        return JSONResponse({"ok": False, "error": "Too many requests"}, status_code=429)
    origin = (origin or "")[:200]
    destination = (destination or "")[:200]
    departure_time = (departure_time or "")[:50]
    seats = max(1, min(10, seats))
    contact = (contact or "")[:50]
    notes = (notes or "")[:500]
    ride = RideShare(
        origin=origin, destination=destination,
        departure_time=departure_time, seats=seats,
        contact=contact, notes=notes,
    )
    post_rideshare(ride)
    return JSONResponse({"ok": True, "ride": ride.to_dict()})


@app.post("/api/alerts/test")
async def api_test_alert(request: Request):
    ip = _client_ip(request)
    if not _rate_limit_check(ip):
        return JSONResponse({"ok": False, "error": "Rate limited. Try again in a minute."}, status_code=429)
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"ok": False, "error": "Invalid JSON"}, status_code=400)

    phone = (body.get("phone") or "").strip().replace(" ", "")[:20]
    channel = (body.get("channel") or "whatsapp").strip()

    if not phone or not phone.startswith("+"):
        return JSONResponse({"ok": False, "error": "Phone must start with + and country code (e.g. +13125551234)"}, status_code=400)

    config = AlertConfig()
    if not config.twilio_sid or not config.twilio_token:
        return JSONResponse({"ok": False, "error": "Twilio not configured on server. Set TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN in .env or environment."}, status_code=500)

    if channel == "whatsapp" and not config.twilio_whatsapp_from:
        return JSONResponse({"ok": False, "error": "WhatsApp sender not configured. Set TWILIO_WHATSAPP_FROM (e.g. +14155238886 for sandbox)."}, status_code=500)

    msg = "EVAC ALERT TEST: You will receive WhatsApp alerts when flight statuses change, prices drop, or new routes appear."

    try:
        if channel == "whatsapp":
            await _send_twilio_whatsapp(config, phone, msg)
        else:
            await _send_twilio_sms(config, phone, msg)
        return JSONResponse({"ok": True, "message": f"Test {channel} sent to {phone}"})
    except Exception as e:
        err = str(e).strip()[:300]
        return JSONResponse({"ok": False, "error": err}, status_code=500)


@app.post("/api/alerts/subscribe")
async def api_subscribe_alerts(request: Request):
    ip = _client_ip(request)
    if not _rate_limit_check(ip):
        return JSONResponse({"ok": False, "error": "Rate limited"}, status_code=429)
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"ok": False, "error": "Invalid JSON"}, status_code=400)

    phone = (body.get("phone") or "").strip()[:20]
    if not phone or not phone.startswith("+"):
        return JSONResponse({"ok": False, "error": "Phone must start with + and country code"}, status_code=400)

    # Persist so alerts are sent to this number (survives restarts; used by AlertConfig)
    _save_subscriptions({"whatsapp": phone})
    os.environ["EVAC_ALERT_WHATSAPP"] = phone
    return JSONResponse({"ok": True, "message": f"WhatsApp alerts will be sent to {phone} on route changes."})


@app.get("/api/translations")
async def api_translations(lang: str = "en"):
    return JSONResponse(get_translations(lang))


AIRPORT_TZ = {
    "DMM": 3, "RUH": 3, "JED": 3,
    "IST": 3,
    "PEK": 8, "PVG": 8, "CAN": 8, "SZX": 8, "HKG": 8,
    "ADD": 3, "LHR": 0, "DEL": 5.5, "BKK": 7, "SIN": 8, "KUL": 8,
    "NRT": 9, "ICN": 9, "DOH": 3, "DXB": 4,
}

TZ_LABEL = {
    3: "AST", 8: "CST", 0: "GMT", 5.5: "IST", 7: "ICT", 9: "JST", 4: "GST",
}


def _utc_time_to_local(utc_time_str: str, tz_offset: float) -> str:
    """Convert a UTC time string like '21:30' or '05:40+1' to local time string."""
    if not utc_time_str:
        return ""
    plus_day = "+1" in utc_time_str
    clean = utc_time_str.replace("+1", "").strip()
    try:
        parts = clean.split(":")
        h, m = int(parts[0]), int(parts[1]) if len(parts) > 1 else 0
    except (ValueError, IndexError):
        return utc_time_str
    total_min = h * 60 + m + int(tz_offset * 60)
    if plus_day:
        total_min += 24 * 60
    day_offset = 0
    while total_min >= 24 * 60:
        total_min -= 24 * 60
        day_offset += 1
    while total_min < 0:
        total_min += 24 * 60
        day_offset -= 1
    lh, lm = divmod(total_min, 60)
    label = TZ_LABEL.get(tz_offset, f"UTC+{tz_offset:g}")
    day_tag = f"+{day_offset}d" if day_offset > 0 else ""
    return f"{lh:02d}:{lm:02d} {label}{day_tag}"


def _route_to_dict(route: Route, now: datetime) -> dict:
    wait = 0.0
    if route.next_departure:
        wait = max(0, (route.next_departure - now).total_seconds() / 3600)

    any_over_budget = any(leg.over_budget for leg in route.flight_legs)
    seats_statuses = [leg.seats_available for leg in route.flight_legs]
    if all(s is True for s in seats_statuses) and seats_statuses:
        seats_status = "ok"
    elif any(s is False for s in seats_statuses):
        seats_status = "sold_out"
    else:
        seats_status = "unknown"

    legs_data = []
    for idx, leg in enumerate(route.flight_legs):
        origin_tz = AIRPORT_TZ.get(leg.origin, 3)
        dest_tz = AIRPORT_TZ.get(leg.destination, 8)
        depart_local = _utc_time_to_local(leg.depart_utc, origin_tz)
        arrive_local = _utc_time_to_local(leg.arrive_utc, dest_tz)

        layover_before = None
        if idx > 0 and idx - 1 < len(route.layover_hours):
            layover_before = route.layover_hours[idx - 1]

        legs_data.append({
            "flight": leg.flight_number,
            "airline": leg.airline,
            "from": leg.origin,
            "to": leg.destination,
            "depart_utc": leg.depart_utc,
            "arrive_utc": leg.arrive_utc,
            "depart_local": depart_local,
            "arrive_local": arrive_local,
            "duration": leg.duration_hours,
            "status": leg.status.value,
            "aircraft": leg.aircraft,
            "seats_available": leg.seats_available,
            "over_budget": leg.over_budget,
            "price_economy": leg.price_economy_usd,
            "price_business": leg.price_business_usd,
            "price_source": leg.price_source,
            "layover_before": layover_before,
            "booking_url": leg.booking_url or "",
            "contact": leg.contact or "",
        })

    arrive_label = None
    if route.estimated_arrival:
        dest_tz = 8
        if route.flight_legs:
            dest_tz = AIRPORT_TZ.get(route.flight_legs[-1].destination, 8)
        tz = timezone(timedelta(hours=dest_tz))
        arrive_label = route.estimated_arrival.astimezone(tz).strftime("%a %H:%M") + " " + TZ_LABEL.get(dest_tz, "")

    return {
        "name": route.name,
        "depart_ast": route.depart_ast,
        "arrive_cst": route.arrive_cst,
        "arrive_label": arrive_label,
        "total_hours": round(route.total_hours, 1),
        "wait_hours": round(wait, 1),
        "ground_hours": round(route.ground_hours, 1),
        "flight_hours": round(route.flight_hours, 1),
        "num_stops": route.num_stops,
        "score": round(route.score, 1),
        "reliability": route.reliability.value,
        "risk": route.conflict_proximity.value,
        "price_economy": route.price_economy_usd,
        "price_business": route.price_business_usd,
        "over_budget": any_over_budget,
        "seats_status": seats_status,
        "changed": route.changed,
        "notes": route.notes,
        "booking_urls": route.booking_urls,
        "contacts": route.contacts,
        "legs": legs_data,
        "ground": [
            {"from": s.origin, "to": s.destination, "via": s.via, "hours": s.estimated_hours}
            for s in route.ground_segments
        ],
    }




def start_server(host: str = "0.0.0.0", port: int = 8000):
    import uvicorn
    uvicorn.run(app, host=host, port=port)
