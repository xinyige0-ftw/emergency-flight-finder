"""Rich terminal display for emergency flight results — clean, scannable output."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from .models import (
    AST,
    CST,
    ConflictProximity,
    FlightStatus,
    ReliabilityScore,
    Route,
    Scenario,
)

console = Console()

STALE_MINUTES = 15

STATUS_ICON = {
    FlightStatus.OPERATING: ("[green]OK[/green]"),
    FlightStatus.SCHEDULED: ("[blue]SCHED[/blue]"),
    FlightStatus.LANDED: ("[green]LANDED[/green]"),
    FlightStatus.DELAYED: ("[yellow]DELAY[/yellow]"),
    FlightStatus.UNKNOWN: ("[yellow]?[/yellow]"),
    FlightStatus.CANCELLED: ("[bold red]CANX[/bold red]"),
}

RISK_ICON = {
    ConflictProximity.LOW: "[green]LOW[/green]",
    ConflictProximity.MEDIUM: "[yellow]MED[/yellow]",
    ConflictProximity.HIGH: "[red]HIGH[/red]",
    ConflictProximity.BLOCKED: "[bold red]BLOCKED[/bold red]",
}

REL_ICON = {
    ReliabilityScore.HIGH: "[bold green]HIGH[/bold green]",
    ReliabilityScore.MEDIUM: "[yellow]MED[/yellow]",
    ReliabilityScore.LOW: "[bold red]LOW[/bold red]",
}


def print_header(scenario: Scenario, is_refresh: bool = False) -> None:
    now = datetime.now(timezone.utc).astimezone(AST)
    badge = "  [bold green][REFRESHED][/bold green]" if is_refresh else ""

    console.print()
    console.print(f"[bold red]  EMERGENCY FLIGHT FINDER[/bold red]{badge}")
    console.print(f"  [bold]{scenario.name}[/bold]")
    console.print(f"  [dim]{now.strftime('%a %b %d, %H:%M AST')}  |  Passport: {scenario.user.passport}  |  Budget: ${scenario.user.budget_usd:,.0f}  |  {scenario.user.passengers} pax[/dim]")
    console.print()


def print_airspace(scenario: Scenario) -> None:
    closed = ", ".join(scenario.airspace_closed)
    open_ = ", ".join(scenario.airspace_open)
    restricted = ", ".join(scenario.airspace_restricted) if scenario.airspace_restricted else None

    console.print(f"  [bold red]CLOSED:[/bold red]     {closed}")
    if restricted:
        console.print(f"  [bold yellow]RESTRICTED:[/bold yellow] {restricted}")
    console.print(f"  [bold green]OPEN:[/bold green]       {open_}")
    console.print()


def print_escape_routes(scenario: Scenario) -> None:
    console.print("  [bold]Getting to the airport:[/bold]")
    for route in scenario.escape_routes:
        icon = "[green]>[/green]" if route.status == "likely_open" else "[yellow]?[/yellow]"
        console.print(f"    {icon} {route.origin} -> {route.destination}  [bold]{route.via}[/bold]  (~{route.estimated_hours:.1f}h)")
    console.print()


def print_summary_table(routes: list[Route], now: datetime) -> None:
    """The main output — one clean table showing everything at a glance."""
    console.rule("[bold red] YOUR OPTIONS — FASTEST FIRST [/bold red]")
    console.print()

    table = Table(show_header=True, header_style="bold", show_lines=True, padding=(0, 1))
    table.add_column("#", justify="center", width=3, style="bold")
    table.add_column("Route", min_width=22)
    table.add_column("Departs\n(Saudi)", min_width=12, justify="center")
    table.add_column("Arrives\n(China)", min_width=12, justify="center")
    table.add_column("Total\nTime", justify="center", min_width=6)
    table.add_column("Price\n(Econ)", justify="center", min_width=7)
    table.add_column("Status", justify="center", min_width=8)
    table.add_column("Risk", justify="center", min_width=6)

    for rank, route in enumerate(routes, 1):
        # Status per leg
        statuses = " ".join(STATUS_ICON.get(leg.status, "?") for leg in route.flight_legs)
        risk = RISK_ICON.get(route.conflict_proximity, "?")
        price = f"${route.price_economy_usd:,.0f}" if route.price_economy_usd else "—"
        depart = route.depart_ast.replace(" AST", "") if route.depart_ast else "—"
        arrive = route.arrive_cst.replace(" CST", "") if route.arrive_cst else "—"

        name = route.name
        if route.changed:
            name = f"[bold magenta]* {name}[/bold magenta]"

        total = f"{route.total_hours:.0f}h"

        table.add_row(str(rank), name, depart, arrive, total, price, statuses, risk)

    console.print(table)
    console.print()


def print_routes(routes: list[Route], now: datetime | None = None) -> None:
    if now is None:
        now = datetime.now(timezone.utc)

    console.rule("[bold] DETAILS [/bold]")

    for rank, route in enumerate(routes, 1):
        _print_route_card(rank, route, now)


def _print_route_card(rank: int, route: Route, now: datetime) -> None:
    risk = RISK_ICON.get(route.conflict_proximity, "?")
    rel = REL_ICON.get(route.reliability, "?")

    border = "green" if route.reliability == ReliabilityScore.HIGH else (
        "red" if route.reliability == ReliabilityScore.LOW else "yellow"
    )

    lines: list[str] = []

    # Header line
    changed = " [bold magenta]*CHANGED*[/bold magenta]" if route.changed else ""
    lines.append(f"  Reliability: {rel}  |  Risk: {risk}{changed}")

    # Time line
    dep = route.depart_ast or "—"
    arr = route.arrive_cst or "—"
    lines.append(f"  [bold]Departs {dep}  ->  Arrives {arr}[/bold]")

    # Breakdown
    if route.next_departure:
        wait = max(0, (route.next_departure - now).total_seconds() / 3600)
        parts = [f"wait {wait:.0f}h"]
        if route.ground_hours > 0:
            parts.append(f"ground {route.ground_hours:.1f}h")
        parts.append(f"flight {route.flight_hours:.1f}h")
        if route.num_stops > 0:
            parts.append(f"layover ~{2 * route.num_stops}h")
        lines.append(f"  Total: [bold]{route.total_hours:.0f}h[/bold]  ({' + '.join(parts)})")

    # Price
    econ = f"${route.price_economy_usd:,.0f}" if route.price_economy_usd else "—"
    biz = f"${route.price_business_usd:,.0f}" if route.price_business_usd else "—"
    lines.append(f"  Price: [bold]{econ}[/bold] economy  /  [bold]{biz}[/bold] business")

    # Ground
    if route.ground_segments:
        ground_parts = []
        for seg in route.ground_segments:
            ground_parts.append(f"{seg.origin}->{seg.destination} ({seg.via}, {seg.estimated_hours:.1f}h)")
        lines.append(f"  [cyan]Ground: {' -> '.join(ground_parts)}[/cyan]")

    # Flights
    for leg in route.flight_legs:
        st = STATUS_ICON.get(leg.status, "?")
        dep_local = _utc_to_ast(leg.depart_utc)
        arr_local = _utc_to_cst(leg.arrive_utc)

        stale = ""
        if leg.last_checked:
            age = (datetime.now(timezone.utc) - leg.last_checked).total_seconds() / 60
            if age > STALE_MINUTES:
                stale = f" [bold red][STALE {age:.0f}m][/bold red]"

        lines.append(f"  [bold]{leg.flight_number}[/bold] {leg.airline}  {leg.origin}->{leg.destination}  {dep_local}->{arr_local}  {leg.duration_hours:.1f}h  {st}{stale}")

    # Booking
    if route.booking_urls:
        lines.append(f"  [green]Book: {route.booking_urls[0]}[/green]")
    if route.contacts:
        lines.append(f"  [yellow]Call: {', '.join(route.contacts)}[/yellow]")

    if route.notes:
        lines.append(f"  [dim]{route.notes}[/dim]")

    title = f"#{rank}  {route.name}"
    content = "\n".join(lines)
    console.print(Panel(content, title=title, title_align="left", border_style=border, padding=(0, 1)))


def print_action_steps(scenario: Scenario) -> None:
    console.print()
    console.rule("[bold] WHAT TO DO NOW [/bold]")
    console.print()

    steps = [
        f"Cross to Saudi Arabia via {scenario.escape_routes[0].via if scenario.escape_routes else 'land border'}",
        "Get to Riyadh airport — fly from Dammam (~1h15m) or drive (~4h)",
        "Call the airline to confirm your flight is operating",
        "Book the fastest CONFIRMED option — speed over price",
        "Backup: Turkish Airlines via Istanbul (daily, safest route)",
        "Monitor: flightradar24.com or run [bold]evac find --watch[/bold]",
        "Pack: passport, cash (SAR + USD), phone + charger",
    ]

    for i, step in enumerate(steps, 1):
        console.print(f"  [bold]{i}.[/bold] {step}")

    console.print()


def print_footer() -> None:
    console.print(
        Panel(
            "[yellow]Flight statuses change rapidly during conflicts. "
            "Always confirm with the airline before heading to the airport.[/yellow]",
            border_style="yellow",
            padding=(0, 1),
        )
    )


def print_watch_banner(interval: int, cycle: int) -> None:
    now_ast = datetime.now(timezone.utc).astimezone(AST)
    console.print()
    console.rule(
        f"[bold cyan]WATCH MODE  |  Cycle #{cycle}  |  "
        f"Refreshes every {interval}m  |  "
        f"{now_ast.strftime('%H:%M AST')}[/bold cyan]"
    )


def print_offline_banner(last_updated: datetime | None) -> None:
    if last_updated:
        age = (datetime.now(timezone.utc) - last_updated).total_seconds() / 60
        console.print(
            f"\n  [bold red]OFFLINE[/bold red] — showing data from {age:.0f}m ago\n"
        )


def _utc_to_ast(utc_str: str) -> str:
    return _utc_to_tz(utc_str, 3, "AST")


def _utc_to_cst(utc_str: str) -> str:
    return _utc_to_tz(utc_str, 8, "CST")


def _utc_to_tz(utc_str: str, offset: int, label: str) -> str:
    clean = utc_str.replace("+1", "").strip()
    if not clean:
        return "—"
    try:
        parts = clean.split(":")
        h, m = int(parts[0]), int(parts[1])
        next_day = "+1" in utc_str
        local_h = h + offset + (24 if next_day else 0)
        day = ""
        if local_h >= 24:
            local_h -= 24
            day = "+1"
        return f"{local_h:02d}:{m:02d}{day}"
    except (ValueError, IndexError):
        return utc_str
