"""FastAPI web server — mobile-first UI for Emergency Flight Finder."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse

from .config import load_scenario
from .models import AST, Route
from .routes import build_routes
from .searcher import check_all_flights

app = FastAPI(title="Emergency Flight Finder")

SCENARIOS_DIR = Path(__file__).parent.parent / "scenarios"
STATIC_DIR = Path(__file__).parent.parent / "static"

_previous_routes: list[Route] = []


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
    }
    return JSONResponse(result)


def _route_to_dict(route: Route, now: datetime) -> dict:
    wait = 0.0
    if route.next_departure:
        wait = max(0, (route.next_departure - now).total_seconds() / 3600)

    return {
        "name": route.name,
        "depart_ast": route.depart_ast,
        "arrive_cst": route.arrive_cst,
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
        "changed": route.changed,
        "notes": route.notes,
        "booking_urls": route.booking_urls,
        "contacts": route.contacts,
        "legs": [
            {
                "flight": leg.flight_number,
                "airline": leg.airline,
                "from": leg.origin,
                "to": leg.destination,
                "depart_utc": leg.depart_utc,
                "arrive_utc": leg.arrive_utc,
                "duration": leg.duration_hours,
                "status": leg.status.value,
                "aircraft": leg.aircraft,
            }
            for leg in route.flight_legs
        ],
        "ground": [
            {"from": s.origin, "to": s.destination, "via": s.via, "hours": s.estimated_hours}
            for s in route.ground_segments
        ],
    }


def start_server(host: str = "0.0.0.0", port: int = 8000):
    import uvicorn
    uvicorn.run(app, host=host, port=port)
