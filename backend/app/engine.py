"""Status engine: pure functions, no I/O. "Today" is always passed in.

Given the car, its items and every log, it answers one question per schedule:
is it ok, upcoming (yellow), due (orange), overdue (red), without history
(grey) or done (one-time, finished)?
"""

from __future__ import annotations

import calendar
import math
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import date, timedelta

from .models import (
    Car,
    Dashboard,
    FuelLog,
    Item,
    MaintenanceRecord,
    OdometerReading,
    Schedule,
    ScheduleEvent,
    ScheduleStatus,
    TriggerStatus,
)

ONE_TIME_LEAD_KM = 500
ONE_TIME_LEAD_DAYS = 30
DAYS_PER_MONTH_FOR_LEAD = 30
STALE_AFTER_DAYS = 30
PACE_WINDOW_DAYS = 90
PACE_MIN_SPAN_DAYS = 7
MAX_OCCURRENCES = 2000

_SEVERITY = {"ok": 0, "upcoming": 1, "due": 2, "overdue": 3}
_NOTIFY_ORDER = {"overdue": 0, "due": 1, "upcoming": 2, "no_history": 3}


@dataclass(frozen=True)
class Point:
    """A moment in the car's life: a date, an odometer value, or both."""

    date: date | None
    km: int | None


@dataclass
class Snapshot:
    """Everything stored for one car."""

    car: Car
    items: list[Item] = field(default_factory=list)
    fuel: list[FuelLog] = field(default_factory=list)
    odometer: list[OdometerReading] = field(default_factory=list)
    maintenance: list[MaintenanceRecord] = field(default_factory=list)
    events: list[ScheduleEvent] = field(default_factory=list)


@dataclass
class Context:
    today: date
    current_km: int
    last_reading_date: date
    pace: float | None
    fuel_points: list[Point]
    completions: dict[str, list[Point]]  # item id -> maintenance records
    skips: dict[str, list[Point]]  # schedule id -> skip events
    snoozes: dict[str, list[ScheduleEvent]]  # schedule id -> snooze events


# --- Date helpers ----------------------------------------------------------


def add_months(d: date, months: int) -> date:
    """Add calendar months, clamping the day to the end of the month."""
    index = d.year * 12 + (d.month - 1) + months
    year, month = divmod(index, 12)
    month += 1
    return date(year, month, min(d.day, calendar.monthrange(year, month)[1]))


def pinned_date(year: int, month: int, day: int) -> date:
    return date(year, month, min(day, calendar.monthrange(year, month)[1]))


def fmt_km(km: int) -> str:
    """Km the way the pt-BR UI writes it: 93.400 km."""
    return f"{km:,}".replace(",", ".") + " km"


def ten_percent(value: float) -> int:
    """10% of an interval, never less than one unit."""
    return max(1, round(value * 0.1))


# --- Thresholds ------------------------------------------------------------


def km_lead(s: Schedule) -> int:
    if s.lead_km is not None:
        return s.lead_km
    if s.type == "interval" and s.every_km:
        return ten_percent(s.every_km)
    return ONE_TIME_LEAD_KM


def km_margin(s: Schedule) -> int:
    if s.overdue_km is not None:
        return s.overdue_km
    if s.type == "interval" and s.every_km:
        return ten_percent(s.every_km)
    return ONE_TIME_LEAD_KM


def _default_days(s: Schedule) -> int:
    if s.type == "interval" and s.every_months:
        return ten_percent(s.every_months * DAYS_PER_MONTH_FOR_LEAD)
    if s.type == "yearly" and s.months:
        return ten_percent(12 * DAYS_PER_MONTH_FOR_LEAD / len(s.months))
    return ONE_TIME_LEAD_DAYS


def day_lead(s: Schedule) -> int:
    return s.lead_days if s.lead_days is not None else _default_days(s)


def day_margin(s: Schedule) -> int:
    return s.overdue_days if s.overdue_days is not None else _default_days(s)


def fillup_lead(n: int) -> int:
    return min(ten_percent(n), n - 1)


def fillup_margin(n: int) -> int:
    return ten_percent(n)


def level(current: int, due: int, lead: int, margin: int) -> str:
    """Status of one trigger from how far `current` is along towards `due`."""
    if current >= due + margin:
        return "overdue"
    if current >= due:
        return "due"
    if current >= due - lead:
        return "upcoming"
    return "ok"


# --- Readings, current km and pace -----------------------------------------


def readings(snapshot: Snapshot) -> list[Point]:
    """Every odometer value we know, including the car's starting point."""
    points = [Point(snapshot.car.start_date, snapshot.car.start_km)]
    points += [Point(f.date, f.km) for f in snapshot.fuel]
    points += [Point(o.date, o.km) for o in snapshot.odometer]
    points += [Point(m.date, m.km) for m in snapshot.maintenance]
    return points


def current_km(snapshot: Snapshot) -> int:
    return max(p.km for p in readings(snapshot))


def compute_pace(points: list[Point], today: date) -> float | None:
    """Km per day over the last 90 days, falling back to all readings."""
    ordered = sorted(set(points), key=lambda p: (p.date, p.km))

    def pace_of(pts: list[Point]) -> float | None:
        if len(pts) < 2:
            return None
        span = (pts[-1].date - pts[0].date).days
        if span < PACE_MIN_SPAN_DAYS:
            return None
        return max(0, pts[-1].km - pts[0].km) / span

    window_start = today - timedelta(days=PACE_WINDOW_DAYS)
    recent = pace_of([p for p in ordered if p.date >= window_start])
    return recent if recent is not None else pace_of(ordered)


# --- Triggers --------------------------------------------------------------


def _km_trigger(due_km: int, ctx: Context, lead: int, margin: int) -> TriggerStatus:
    remaining = due_km - ctx.current_km
    projected = None
    if remaining > 0 and ctx.pace:
        days = math.ceil(remaining / ctx.pace)
        projected = max(ctx.today, ctx.last_reading_date + timedelta(days=days))
    return TriggerStatus(
        kind="km",
        status=level(ctx.current_km, due_km, lead, margin),
        remaining=remaining,
        due_km=due_km,
        projected_date=projected,
    )


def _date_trigger(due_date: date, ctx: Context, lead: int, margin: int) -> TriggerStatus:
    return TriggerStatus(
        kind="date",
        status=level(ctx.today.toordinal(), due_date.toordinal(), lead, margin),
        remaining=(due_date - ctx.today).days,
        due_date=due_date,
    )


def _fillups_trigger(every: int, count: int) -> TriggerStatus:
    return TriggerStatus(
        kind="fillups",
        status=level(count, every, fillup_lead(every), fillup_margin(every)),
        remaining=every - count,
        due_fillups=every,
    )


def _point_key(p: Point) -> tuple[date, int]:
    return (p.date or date.min, p.km if p.km is not None else -1)


def count_fillups_after(fuel_points: list[Point], base: Point) -> int:
    """Fuel logs strictly after the baseline. Same day and same km does not count."""
    key = _point_key(base)
    return sum(1 for f in fuel_points if _point_key(f) > key)


def _actual_triggers(s: Schedule, base: Point, ctx: Context) -> list[TriggerStatus]:
    triggers: list[TriggerStatus] = []
    if s.every_km and base.km is not None:
        triggers.append(_km_trigger(base.km + s.every_km, ctx, km_lead(s), km_margin(s)))
    if s.every_months and base.date is not None:
        due = add_months(base.date, s.every_months)
        triggers.append(_date_trigger(due, ctx, day_lead(s), day_margin(s)))
    if s.every_fillups and base.date is not None:
        count = count_fillups_after(ctx.fuel_points, base)
        triggers.append(_fillups_trigger(s.every_fillups, count))
    return triggers


def occurrences(s: Schedule) -> Iterator[tuple[int | None, date | None]]:
    """Due points (km, date) of a fixed, yearly or one-time schedule, in order."""
    if s.type == "one_time":
        yield (s.at_km, s.on_date)
    elif s.type == "yearly":
        produced = 0
        year = s.created_on.year
        while produced < MAX_OCCURRENCES:
            for month in s.months:
                d = pinned_date(year, month, s.day)
                if d >= s.created_on:
                    produced += 1
                    yield (None, d)
            year += 1
    else:
        for k in range(MAX_OCCURRENCES):
            due_km = s.first_due_km + k * s.every_km if s.every_km else None
            due_date = (
                add_months(s.first_due_date, k * s.every_months) if s.every_months else None
            )
            yield (due_km, due_date)


def _pending_occurrence(
    s: Schedule, completions: list[Point]
) -> tuple[int | None, date | None] | None:
    """First due point not cleared by a completion.

    A completion clears a due point only when made at or after that point's
    yellow threshold, so early work never cancels a later fixed event.
    """
    last_date = max((p.date for p in completions if p.date is not None), default=None)
    last_km = max((p.km for p in completions if p.km is not None), default=None)
    lead_d, lead_k = day_lead(s), km_lead(s)
    for due_km, due_date in occurrences(s):
        cleared_by_date = (
            due_date is not None
            and last_date is not None
            and last_date >= due_date - timedelta(days=lead_d)
        )
        cleared_by_km = due_km is not None and last_km is not None and last_km >= due_km - lead_k
        if not (cleared_by_date or cleared_by_km):
            return (due_km, due_date)
    return None


def _worst(triggers: list[TriggerStatus]) -> TriggerStatus:
    return max(triggers, key=lambda t: _SEVERITY[t.status])


def _active_snooze(snoozes: list[ScheduleEvent], ref_date: date | None) -> ScheduleEvent | None:
    """Latest snooze made after the last completion; older ones are spent."""
    live = [e for e in snoozes if ref_date is None or e.date > ref_date]
    return max(live, key=lambda e: (e.date, e.created_at)) if live else None


# --- One schedule ----------------------------------------------------------


def evaluate_schedule(item: Item, s: Schedule, ctx: Context) -> ScheduleStatus:
    result = ScheduleStatus(
        item_id=item.id,
        item_name=item.name,
        jp_term=item.jp_term,
        schedule_id=s.id,
        schedule_type=s.type,
        status="no_history",
        raw_status="no_history",
    )
    completions = ctx.completions.get(item.id, []) + ctx.skips.get(s.id, [])

    if s.type == "interval" and s.anchor == "actual":
        candidates = list(completions)
        if s.baseline_date is not None or s.baseline_km is not None:
            candidates.append(Point(s.baseline_date, s.baseline_km))
        if not candidates:
            return result
        base = max(candidates, key=_point_key)
        triggers = _actual_triggers(s, base, ctx)
        if not triggers:
            return result
        last_done: Point | None = base
    else:
        last_done = max(completions, key=_point_key) if completions else None
        pending = _pending_occurrence(s, completions)
        if pending is None:
            result.status = result.raw_status = "done"
            if last_done:
                result.last_done_date, result.last_done_km = last_done.date, last_done.km
            return result
        due_km, due_date = pending
        triggers = []
        if due_km is not None:
            triggers.append(_km_trigger(due_km, ctx, km_lead(s), km_margin(s)))
        if due_date is not None:
            triggers.append(_date_trigger(due_date, ctx, day_lead(s), day_margin(s)))

    result.raw_status = _worst(triggers).status
    if last_done:
        result.last_done_date, result.last_done_km = last_done.date, last_done.km

    snooze = _active_snooze(ctx.snoozes.get(s.id, []), last_done.date if last_done else None)
    if snooze:
        snoozed: list[TriggerStatus] = []
        if snooze.until_km is not None:
            snoozed.append(_km_trigger(snooze.until_km, ctx, km_lead(s), km_margin(s)))
        if snooze.until_date is not None:
            snoozed.append(_date_trigger(snooze.until_date, ctx, day_lead(s), day_margin(s)))
        if snoozed:
            triggers = snoozed
            result.snoozed = True
            result.snooze_until_km = snooze.until_km
            result.snooze_until_date = snooze.until_date

    worst = _worst(triggers)
    result.triggers = triggers
    result.status = worst.status
    result.driving = worst.kind
    estimates = [t.due_date for t in triggers if t.due_date is not None]
    estimates += [t.projected_date for t in triggers if t.projected_date is not None]
    result.estimated_due_date = min(estimates) if estimates else None
    return result


# --- The whole car ---------------------------------------------------------


def build_context(snapshot: Snapshot, today: date) -> Context:
    points = readings(snapshot)
    completions: dict[str, list[Point]] = {}
    for record in snapshot.maintenance:
        for item_id in record.item_ids:
            completions.setdefault(item_id, []).append(Point(record.date, record.km))
    skips: dict[str, list[Point]] = {}
    snoozes: dict[str, list[ScheduleEvent]] = {}
    for event in snapshot.events:
        if event.type == "skip":
            skips.setdefault(event.schedule_id, []).append(Point(event.date, event.km))
        else:
            snoozes.setdefault(event.schedule_id, []).append(event)
    return Context(
        today=today,
        current_km=max(p.km for p in points),
        last_reading_date=max(p.date for p in points),
        pace=compute_pace(points, today),
        fuel_points=[Point(f.date, f.km) for f in snapshot.fuel],
        completions=completions,
        skips=skips,
        snoozes=snoozes,
    )


def evaluate_all(snapshot: Snapshot, today: date) -> list[ScheduleStatus]:
    ctx = build_context(snapshot, today)
    return [
        evaluate_schedule(item, s, ctx)
        for item in snapshot.items
        if not item.archived
        for s in item.schedules
        if s.active
    ]


def build_dashboard(snapshot: Snapshot, today: date) -> Dashboard:
    ctx = build_context(snapshot, today)
    statuses = evaluate_all(snapshot, today)
    notifications = sorted(
        (s for s in statuses if s.status in _NOTIFY_ORDER),
        key=lambda s: (_NOTIFY_ORDER[s.status], s.item_name.lower()),
    )
    days_since = max(0, (today - ctx.last_reading_date).days)
    estimated = None
    if ctx.pace is not None:
        estimated = ctx.current_km + round(ctx.pace * days_since)
    return Dashboard(
        today=today,
        current_km=ctx.current_km,
        last_reading_date=ctx.last_reading_date,
        estimated_km=estimated,
        pace_km_per_day=round(ctx.pace, 2) if ctx.pace is not None else None,
        stale=days_since > STALE_AFTER_DAYS,
        notifications=notifications,
        statuses=statuses,
    )


# --- Odometer order --------------------------------------------------------


def check_km_order(
    entry_date: date, km: int, others: list[Point], start_km: int
) -> str | None:
    """Return an error message when `km` breaks the odometer order, else None.

    The odometer never goes backwards: an entry must be at least the highest km
    logged on an earlier date and at most the lowest km logged on a later date.
    """
    if km < start_km:
        return f"O km não pode ser menor que o km inicial do carro ({fmt_km(start_km)})."
    before = [p.km for p in others if p.date < entry_date]
    after = [p.km for p in others if p.date > entry_date]
    if before and km < max(before):
        return (
            "O km não pode ser menor que o já registrado antes dessa data "
            f"({fmt_km(max(before))})."
        )
    if after and km > min(after):
        return (
            "O km não pode ser maior que o registrado depois dessa data "
            f"({fmt_km(min(after))})."
        )
    return None
