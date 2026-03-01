"""CLI entry point for the Emergency Flight Finder."""
from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone
from pathlib import Path

import click
from rich.console import Console

from .config import load_scenario
from .display import (
    print_action_steps,
    print_airspace,
    print_escape_routes,
    print_footer,
    print_header,
    print_offline_banner,
    print_routes,
    print_summary_table,
    print_watch_banner,
)
from .alerts import AlertConfig, detect_changes, send_alerts, print_alert_status
from .models import Route, UserProfile
from .pricing import check_prices_and_seats, filter_by_budget, check_multi_passenger_availability
from .routes import build_routes
from .searcher import check_all_flights

console = Console()

SCENARIOS_DIR = Path(__file__).parent.parent / "scenarios"


@click.group()
def cli() -> None:
    """Emergency Flight Finder — fastest way out of a conflict zone."""
    pass


@cli.command()
def list_scenarios() -> None:
    """List available scenario files."""
    if not SCENARIOS_DIR.exists():
        console.print("[red]No scenarios directory found.[/red]")
        return
    for f in sorted(SCENARIOS_DIR.glob("*.yaml")):
        console.print(f"  [bold]{f.stem}[/bold] — {f}")


@cli.command()
@click.argument("scenario_file", type=click.Path(exists=True), required=False)
@click.option("--scenario", "-s", default=None, help="Scenario name from scenarios/ dir")
# --- Live / watch ---
@click.option("--live/--offline", default=True, help="Check live flight statuses (default: live)")
@click.option("--watch", "-w", is_flag=True, default=False, help="Auto-refresh mode")
@click.option("--refresh-interval", "-r", default=5, type=int, help="Refresh interval in minutes (1-60, default: 5)")
# --- User criteria (all have defaults, all toggleable) ---
@click.option("--passengers", "-p", default=1, type=int, help="Number of passengers (default: 1)")
@click.option("--passport", default="CN", type=str, help="Passport country code (default: CN)")
@click.option("--budget", "-b", default=10000, type=float, help="Max budget in USD (default: 10000)")
@click.option("--destination", "-d", default="anywhere", type=str, help="Destination preference: anywhere, south, east, north, or airport code (default: anywhere)")
@click.option("--risk", default="moderate", type=click.Choice(["avoid_all", "moderate", "pragmatic"]), help="Risk tolerance (default: moderate)")
@click.option("--speed", default="balanced", type=click.Choice(["soonest", "shortest_total", "balanced"]), help="Speed priority (default: balanced)")
@click.option("--sort", "sort_by", default="score", type=click.Choice(["score", "depart", "price", "duration"]), help="Sort routes by (default: score)")
@click.option("--max-stops", default=2, type=int, help="Max number of stops (default: 2)")
@click.option("--max-wait", default=72, type=float, help="Max hours willing to wait for a flight (default: 72)")
@click.option("--show-cancelled/--hide-cancelled", default=True, help="Show cancelled flights (default: show)")
def find(
    scenario_file: str | None,
    scenario: str | None,
    live: bool,
    watch: bool,
    refresh_interval: int,
    passengers: int,
    passport: str,
    budget: float,
    destination: str,
    risk: str,
    speed: str,
    sort_by: str,
    max_stops: int,
    max_wait: float,
    show_cancelled: bool,
) -> None:
    """Find the fastest escape routes. All criteria can be overridden via flags."""
    path = _resolve_scenario(scenario_file, scenario)
    if path is None:
        return

    overrides = {
        "passengers": passengers,
        "passport": passport.upper(),
        "budget_usd": budget,
        "destination_flex": destination,
        "risk_tolerance": risk,
        "speed_priority": speed,
        "sort_by": sort_by,
        "max_stops": max_stops,
        "max_wait_hours": max_wait,
        "show_cancelled": show_cancelled,
    }

    refresh_interval = max(1, min(60, refresh_interval))

    if watch:
        asyncio.run(_run_watch(path, live, refresh_interval, overrides))
    else:
        asyncio.run(_run_finder(path, live, overrides=overrides))


async def _run_finder(
    path: Path,
    live: bool,
    previous_routes: list[Route] | None = None,
    is_refresh: bool = False,
    overrides: dict | None = None,
) -> list[Route]:
    now = datetime.now(timezone.utc)
    overrides = overrides or {}

    sc = load_scenario(path)

    # Apply CLI overrides to user profile
    sc.user.passengers = overrides.get("passengers", sc.user.passengers)
    sc.user.passport = overrides.get("passport", sc.user.passport)
    sc.user.budget_usd = overrides.get("budget_usd", sc.user.budget_usd)
    sc.user.destination_flex = overrides.get("destination_flex", sc.user.destination_flex)
    sc.user.risk_tolerance = overrides.get("risk_tolerance", sc.user.risk_tolerance)

    print_header(sc, is_refresh=is_refresh)
    print_airspace(sc)
    print_escape_routes(sc)

    try:
        sc.known_flights = await check_all_flights(sc.known_flights, live=live)
        sc.known_flights = await check_prices_and_seats(
            sc.known_flights,
            passengers=overrides.get("passengers", 1),
            live=live,
        )
        sc.known_flights = filter_by_budget(
            sc.known_flights, sc.user.budget_usd, sc.user.passengers,
        )
        sc.known_flights = check_multi_passenger_availability(
            sc.known_flights, overrides.get("passengers", 1),
        )
    except Exception as e:
        console.print(f"[bold red]Network error: {e}[/bold red]")
        print_offline_banner(now if not is_refresh else None)

    routes = build_routes(
        sc,
        now=now,
        previous_routes=previous_routes,
        speed_mode=overrides.get("speed_priority", "balanced"),
        max_stops=overrides.get("max_stops", 2),
        max_wait_hours=overrides.get("max_wait_hours", 72),
    )

    # Filter cancelled if requested
    if not overrides.get("show_cancelled", True):
        routes = [r for r in routes if r.reliability.value != "low"]

    # Re-sort if user wants a different sort order
    sort_key = overrides.get("sort_by", "score")
    if sort_key == "depart":
        routes.sort(key=lambda r: r.next_departure or datetime.max.replace(tzinfo=timezone.utc))
    elif sort_key == "price":
        routes.sort(key=lambda r: r.price_economy_usd or 99999)
    elif sort_key == "duration":
        routes.sort(key=lambda r: r.flight_hours)

    if not routes:
        console.print("[bold red]No viable routes found![/bold red]")
        return []

    if any(r.changed for r in routes):
        console.bell()
        console.print("\n[bold magenta]*** STATUS CHANGED ***[/bold magenta]\n")

    print_summary_table(routes, now)
    print_routes(routes, now=now)
    print_action_steps(sc)
    print_footer()

    return routes


async def _run_watch(path: Path, live: bool, interval_minutes: int, overrides: dict) -> None:
    cycle = 0
    previous_routes: list[Route] | None = None
    alert_config = AlertConfig()

    print_alert_status(alert_config)

    while True:
        cycle += 1
        console.clear()
        routes = await _run_finder(
            path, live,
            previous_routes=previous_routes,
            is_refresh=cycle > 1,
            overrides=overrides,
        )

        if previous_routes and alert_config.is_configured:
            changes = detect_changes(routes, previous_routes)
            if changes:
                sent = await send_alerts(changes, alert_config)
                if sent:
                    console.print(f"[green]Sent {sent} alert(s)[/green]")

        previous_routes = routes
        print_watch_banner(interval_minutes, cycle)

        try:
            for remaining in range(interval_minutes * 60, 0, -1):
                mins, secs = divmod(remaining, 60)
                print(f"\r  Next refresh in {mins}m {secs:02d}s ... (Ctrl+C to stop)", end="", flush=True)
                time.sleep(1)
            print()
        except KeyboardInterrupt:
            console.print("\n[bold]Watch mode stopped.[/bold]")
            break


@cli.command()
@click.argument("flight_number")
@click.option("--watch", "-w", is_flag=True, default=False, help="Keep checking")
@click.option("--refresh-interval", "-r", default=2, type=int, help="Minutes between checks (default: 2)")
def status(flight_number: str, watch: bool, refresh_interval: int) -> None:
    """Check live status of a single flight (e.g., CX644, SV884)."""
    from .models import FlightLeg
    from .searcher import check_flight_status_fr24

    flight = FlightLeg(flight_number=flight_number.upper(), airline="Unknown", origin="", destination="")

    async def _check():
        prev = None
        while True:
            result = await check_flight_status_fr24(flight)
            label, style = {
                "operating": ("OPERATING", "bold green"), "scheduled": ("SCHEDULED", "bold blue"),
                "cancelled": ("CANCELLED", "bold red"), "delayed": ("DELAYED", "bold yellow"),
                "unknown": ("UNKNOWN", "yellow"), "landed": ("LANDED", "green"),
            }.get(result.status.value, ("UNKNOWN", "dim"))

            changed = prev is not None and prev != result.status.value
            badge = " [bold magenta]*CHANGED*[/bold magenta]" if changed else ""
            console.print(f"[bold]{flight_number.upper()}[/bold]: [{style}]{label}[/{style}]{badge}")
            if result.last_checked:
                console.print(f"  [dim]{result.last_checked.strftime('%H:%M UTC')} via {result.status_source}[/dim]")
            if changed:
                console.bell()
            prev = result.status.value

            if not watch:
                break
            try:
                for remaining in range(refresh_interval * 60, 0, -1):
                    mins, secs = divmod(remaining, 60)
                    print(f"\r  Next check in {mins}m {secs:02d}s ... (Ctrl+C to stop)", end="", flush=True)
                    time.sleep(1)
                print()
            except KeyboardInterrupt:
                console.print("\n[bold]Stopped.[/bold]")
                break

    asyncio.run(_check())


def _resolve_scenario(scenario_file: str | None, scenario_name: str | None) -> Path | None:
    if scenario_file:
        return Path(scenario_file)
    if scenario_name:
        path = SCENARIOS_DIR / f"{scenario_name}.yaml"
        if path.exists():
            return path
        console.print(f"[red]Scenario '{scenario_name}' not found at {path}[/red]")
        return None
    yamls = list(SCENARIOS_DIR.glob("*.yaml"))
    if yamls:
        return yamls[0]
    console.print("[red]No scenario file found. Use: evac find -s bahrain_to_china[/red]")
    return None


@cli.command()
@click.option("--host", default="0.0.0.0", help="Bind host (default: 0.0.0.0)")
@click.option("--port", default=8000, type=int, help="Port (default: 8000)")
def serve(host: str, port: int) -> None:
    """Start the mobile web UI server."""
    import socket
    import uvicorn
    from .web import app

    local_ip = _get_local_ip()
    console.print(f"[bold green]Starting web UI...[/bold green]")
    console.print(f"[bold]Open on your phone:[/bold] [underline]http://{local_ip}:{port}[/underline]")
    console.print(f"[dim]Local: http://localhost:{port}[/dim]")
    uvicorn.run(app, host=host, port=port)


def _get_local_ip() -> str:
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "localhost"


def main() -> None:
    cli()
