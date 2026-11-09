"""Small builders so each test states only what matters to it."""

from __future__ import annotations

import itertools
from datetime import date, timedelta

from app.engine import Snapshot, build_dashboard, evaluate_all
from app.models import (
    Car,
    Dashboard,
    FuelLog,
    Item,
    MaintenanceRecord,
    OdometerReading,
    Schedule,
    ScheduleEvent,
    ScheduleStatus,
)

TODAY = date(2026, 11, 9)
START_DATE = date(2026, 1, 1)
START_KM = 93_000

_ids = itertools.count(1)


def days_ago(n: int, today: date = TODAY) -> date:
    return today - timedelta(days=n)


def car(start_km: int = START_KM, start_date: date = START_DATE) -> Car:
    return Car(maker="Toyota", model="Prius", start_km=start_km, start_date=start_date)


def sched(id: str = "s1", type: str = "interval", **kwargs) -> Schedule:
    kwargs.setdefault("created_on", START_DATE)
    return Schedule(id=id, type=type, **kwargs)


def item(*schedules: Schedule, id: str = "i1", name: str = "Óleo do motor", **kwargs) -> Item:
    return Item(id=id, name=name, jp_term="エンジンオイル交換", schedules=list(schedules), **kwargs)


def fuel(d: date, km: int, **kwargs) -> FuelLog:
    return FuelLog(id=f"f{next(_ids)}", date=d, km=km, **kwargs)


def odo(d: date, km: int) -> OdometerReading:
    return OdometerReading(id=f"o{next(_ids)}", date=d, km=km)


def maint(d: date, km: int, *item_ids: str) -> MaintenanceRecord:
    return MaintenanceRecord(id=f"m{next(_ids)}", date=d, km=km, item_ids=list(item_ids or ["i1"]))


def skip(d: date, km: int, schedule_id: str = "s1", item_id: str = "i1") -> ScheduleEvent:
    n = next(_ids)
    return ScheduleEvent(
        id=f"e{n}",
        type="skip",
        item_id=item_id,
        schedule_id=schedule_id,
        date=d,
        km=km,
        created_at=f"{n:08d}",
    )


def snooze(
    d: date,
    km: int,
    until_km: int | None = None,
    until_date: date | None = None,
    schedule_id: str = "s1",
    item_id: str = "i1",
) -> ScheduleEvent:
    n = next(_ids)
    return ScheduleEvent(
        id=f"e{n}",
        type="snooze",
        item_id=item_id,
        schedule_id=schedule_id,
        date=d,
        km=km,
        until_km=until_km,
        until_date=until_date,
        created_at=f"{n:08d}",
    )


def snap(
    items=(), fuel=(), odometer=(), maintenance=(), events=(), car_: Car | None = None
) -> Snapshot:
    return Snapshot(
        car=car_ or car(),
        items=list(items),
        fuel=list(fuel),
        odometer=list(odometer),
        maintenance=list(maintenance),
        events=list(events),
    )


def status_of(snapshot: Snapshot, today: date = TODAY, schedule_id: str = "s1") -> ScheduleStatus:
    for status in evaluate_all(snapshot, today):
        if status.schedule_id == schedule_id:
            return status
    raise AssertionError(f"schedule {schedule_id} was not evaluated")


def dashboard(snapshot: Snapshot, today: date = TODAY) -> Dashboard:
    return build_dashboard(snapshot, today)


def trigger(status: ScheduleStatus, kind: str):
    for t in status.triggers:
        if t.kind == kind:
            return t
    raise AssertionError(f"no {kind} trigger in {status.triggers}")
