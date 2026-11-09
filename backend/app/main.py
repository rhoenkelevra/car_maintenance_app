"""HTTP API. All rules live in engine.py; this file validates, stores and wires."""

from __future__ import annotations

import os
import uuid
from contextlib import asynccontextmanager
from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from . import seed as seed_data
from .engine import (
    Point,
    Snapshot,
    build_dashboard,
    check_km_order,
    current_km,
    evaluate_all,
    fmt_km,
)
from .models import (
    BaselineIn,
    Car,
    Dashboard,
    FuelLog,
    FuelLogIn,
    HistoryEntry,
    Item,
    ItemIn,
    MaintenanceIn,
    MaintenanceRecord,
    OdometerIn,
    OdometerReading,
    Schedule,
    ScheduleEvent,
    ScheduleStatus,
    SkipIn,
    SnoozeIn,
)
from .store import Store, get_table

TIMEZONE = ZoneInfo("Asia/Tokyo")


# --- Dependencies ----------------------------------------------------------


def get_store() -> Store:
    return Store(get_table())


def get_today() -> date:
    return datetime.now(TIMEZONE).date()


def new_id() -> str:
    return uuid.uuid4().hex[:12]


def require_snapshot(store: Store = Depends(get_store)) -> Snapshot:
    snapshot = store.load()
    if snapshot is None:
        raise HTTPException(409, "Cadastre o carro primeiro.")
    return snapshot


# --- App -------------------------------------------------------------------


@asynccontextmanager
async def lifespan(_: FastAPI):
    if os.environ.get("DYNAMODB_ENDPOINT"):
        get_table()  # creates the table locally when missing
    yield


app = FastAPI(title="Car Maintenance", lifespan=lifespan)
api = APIRouter(prefix="/api")


def _clean(message: str) -> str:
    return message.removeprefix("Value error, ")


FIELD_LABELS = {
    "date": "Data",
    "km": "Km",
    "litres": "Litros",
    "price_total": "Valor total",
    "name": "Nome",
    "item_ids": "Itens",
    "cost_total": "Custo",
    "maker": "Marca",
    "model": "Modelo",
    "year": "Ano",
    "tank_l": "Tanque",
    "start_km": "Km inicial",
    "start_date": "Data inicial",
    "shaken_expiry": "Vencimento do shaken",
    "every_km": "Intervalo em km",
    "every_months": "Intervalo em meses",
    "every_fillups": "Intervalo em abastecimentos",
    "day": "Dia",
    "until_km": "Km do adiamento",
    "until_date": "Data do adiamento",
}


def _bound(value) -> str:
    """A limit from a field constraint, without a trailing ".0"."""
    return str(int(value)) if isinstance(value, float) and value.is_integer() else str(value)


def _translate(error: dict) -> str:
    """pt-BR text for the field errors the forms can actually produce."""
    kind, ctx = error.get("type", ""), error.get("ctx") or {}
    if kind == "missing":
        return "campo obrigatório"
    if kind == "greater_than":
        return f"deve ser maior que {_bound(ctx.get('gt'))}"
    if kind == "greater_than_equal":
        return f"deve ser no mínimo {_bound(ctx.get('ge'))}"
    if kind == "less_than_equal":
        return f"deve ser no máximo {_bound(ctx.get('le'))}"
    if kind == "string_too_short":
        return "não pode ficar vazio"
    if kind == "too_short":
        return "escolha ao menos um"
    if kind.startswith(("int_", "float_", "decimal_")):
        return "número inválido"
    if kind.startswith("date_"):
        return "data inválida"
    return _clean(error.get("msg", "dados inválidos"))


@app.exception_handler(RequestValidationError)
async def validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
    """Keep `detail` one plain pt-BR sentence the front end can show as is."""
    errors = exc.errors()
    first = errors[0] if errors else {}
    loc = [p for p in first.get("loc", []) if p != "body"]
    # ("schedules", 0, "every_km") -> "Agenda 1: Intervalo em km: ..."
    prefix = ""
    if len(loc) >= 2 and loc[0] == "schedules" and isinstance(loc[1], int):
        prefix, loc = f"Agenda {loc[1] + 1}: ", loc[2:]
    if first.get("type") == "value_error":
        detail = prefix + _clean(first.get("msg", "Dados inválidos."))
    else:
        field = str(loc[-1]) if loc else ""
        label = FIELD_LABELS.get(field, field)
        message = _translate(first)
        detail = prefix + (f"{label}: {message}" if label else message.capitalize())
    return JSONResponse(status_code=422, content={"detail": detail})


# --- Helpers ---------------------------------------------------------------


def _km_points(snapshot: Snapshot, exclude_id: str | None = None) -> list[Point]:
    entries = [*snapshot.fuel, *snapshot.odometer, *snapshot.maintenance]
    return [Point(e.date, e.km) for e in entries if e.id != exclude_id]


def _validate_entry(
    snapshot: Snapshot, entry_date: date, km: int, today: date, exclude_id: str | None = None
) -> None:
    if entry_date > today:
        raise HTTPException(422, "A data não pode ser no futuro.")
    error = check_km_order(
        entry_date, km, _km_points(snapshot, exclude_id), snapshot.car.start_km
    )
    if error:
        raise HTTPException(422, error)


def _find(collection: list, entity_id: str, what: str):
    for entity in collection:
        if entity.id == entity_id:
            return entity
    raise HTTPException(404, f"{what} não encontrado.")


def _find_schedule(snapshot: Snapshot, item_id: str, schedule_id: str) -> tuple[Item, Schedule]:
    item = _find(snapshot.items, item_id, "Item")
    return item, _find(item.schedules, schedule_id, "Agenda")


def _status_of(snapshot: Snapshot, schedule_id: str, today: date) -> ScheduleStatus | None:
    for status in evaluate_all(snapshot, today):
        if status.schedule_id == schedule_id:
            return status
    return None


def _build_schedules(body: ItemIn, today: date, existing: Item | None) -> list[Schedule]:
    """Give new schedules an id and a creation date; keep both for known ones."""
    known = {s.id: s for s in existing.schedules} if existing else {}
    schedules = []
    for incoming in body.schedules:
        data = incoming.model_dump()
        if incoming.id in known:
            data["created_on"] = known[incoming.id].created_on
        else:
            data["id"] = new_id()
            data["created_on"] = incoming.created_on or today
        schedules.append(Schedule(**data))
    return schedules


def _item_in_use(snapshot: Snapshot, item_id: str) -> bool:
    return any(item_id in m.item_ids for m in snapshot.maintenance) or any(
        e.item_id == item_id for e in snapshot.events
    )


def _check_items_exist(snapshot: Snapshot, item_ids: list[str]) -> None:
    known = {i.id for i in snapshot.items}
    if len(set(item_ids)) != len(item_ids):
        raise HTTPException(422, "Item repetido na manutenção.")
    if any(i not in known for i in item_ids):
        raise HTTPException(422, "Item da manutenção não existe.")


# --- Car -------------------------------------------------------------------


@api.get("/car")
def get_car(store: Store = Depends(get_store)) -> Car | None:
    snapshot = store.load()
    return snapshot.car if snapshot else None


@api.put("/car")
def put_car(car: Car, store: Store = Depends(get_store)) -> Car:
    snapshot = store.load()
    if snapshot:
        logged = [p.km for p in _km_points(snapshot)]
        if logged and car.start_km > min(logged):
            raise HTTPException(
                422,
                f"O km inicial não pode ser maior que o menor km registrado ({fmt_km(min(logged))}).",
            )
    store.put_car(car)
    return car


@api.get("/dashboard")
def get_dashboard(
    snapshot: Snapshot = Depends(require_snapshot), today: date = Depends(get_today)
) -> Dashboard:
    return build_dashboard(snapshot, today)


# --- Items and schedules ---------------------------------------------------


@api.get("/items")
def list_items(
    include_archived: bool = False, snapshot: Snapshot = Depends(require_snapshot)
) -> list[Item]:
    return [i for i in snapshot.items if include_archived or not i.archived]


@api.post("/items", status_code=201)
def create_item(
    body: ItemIn,
    _: Snapshot = Depends(require_snapshot),
    store: Store = Depends(get_store),
    today: date = Depends(get_today),
) -> Item:
    item = Item(
        id=new_id(),
        name=body.name,
        jp_term=body.jp_term,
        notes=body.notes,
        schedules=_build_schedules(body, today, None),
    )
    store.put_item(item)
    return item


@api.get("/items/{item_id}")
def get_item(item_id: str, snapshot: Snapshot = Depends(require_snapshot)) -> Item:
    return _find(snapshot.items, item_id, "Item")


@api.put("/items/{item_id}")
def update_item(
    item_id: str,
    body: ItemIn,
    snapshot: Snapshot = Depends(require_snapshot),
    store: Store = Depends(get_store),
    today: date = Depends(get_today),
) -> Item:
    existing = _find(snapshot.items, item_id, "Item")
    item = existing.model_copy(
        update={
            "name": body.name,
            "jp_term": body.jp_term,
            "notes": body.notes,
            "schedules": _build_schedules(body, today, existing),
        }
    )
    store.put_item(item)
    return item


@api.delete("/items/{item_id}")
def delete_item(
    item_id: str,
    snapshot: Snapshot = Depends(require_snapshot),
    store: Store = Depends(get_store),
) -> dict:
    """Delete an item, or archive it when history refers to it."""
    item = _find(snapshot.items, item_id, "Item")
    if _item_in_use(snapshot, item_id):
        store.put_item(item.model_copy(update={"archived": True}))
        return {"archived": True}
    store.delete_item(item_id)
    return {"archived": False}


@api.post("/items/{item_id}/restore")
def restore_item(
    item_id: str,
    snapshot: Snapshot = Depends(require_snapshot),
    store: Store = Depends(get_store),
) -> Item:
    item = _find(snapshot.items, item_id, "Item").model_copy(update={"archived": False})
    store.put_item(item)
    return item


@api.post("/items/{item_id}/schedules/{schedule_id}/skip", status_code=201)
def skip_schedule(
    item_id: str,
    schedule_id: str,
    body: SkipIn,
    snapshot: Snapshot = Depends(require_snapshot),
    store: Store = Depends(get_store),
    today: date = Depends(get_today),
) -> ScheduleEvent:
    _, schedule = _find_schedule(snapshot, item_id, schedule_id)
    status = _status_of(snapshot, schedule_id, today)
    if status is None or status.status in ("no_history", "done"):
        raise HTTPException(409, "Nada para pular nesta agenda.")
    counts_from_actual = schedule.type == "interval" and schedule.anchor == "actual"
    if not counts_from_actual and status.raw_status == "ok":
        raise HTTPException(409, "Ainda não está no período de aviso.")
    event = ScheduleEvent(
        id=new_id(),
        type="skip",
        item_id=item_id,
        schedule_id=schedule_id,
        date=today,
        km=current_km(snapshot),
        note=body.note,
        created_at=datetime.now(UTC).isoformat(),
    )
    store.put_event(event)
    return event


@api.post("/items/{item_id}/schedules/{schedule_id}/snooze", status_code=201)
def snooze_schedule(
    item_id: str,
    schedule_id: str,
    body: SnoozeIn,
    snapshot: Snapshot = Depends(require_snapshot),
    store: Store = Depends(get_store),
    today: date = Depends(get_today),
) -> ScheduleEvent:
    _find_schedule(snapshot, item_id, schedule_id)
    status = _status_of(snapshot, schedule_id, today)
    if status is None or status.raw_status not in ("upcoming", "due", "overdue"):
        raise HTTPException(409, "Nada para adiar nesta agenda.")
    km_now = current_km(snapshot)
    if body.until_km is not None and body.until_km <= km_now:
        raise HTTPException(
            422, f"O km do adiamento deve ser maior que o km atual ({fmt_km(km_now)})."
        )
    if body.until_date is not None and body.until_date <= today:
        raise HTTPException(422, "A data do adiamento deve ser depois de hoje.")
    event = ScheduleEvent(
        id=new_id(),
        type="snooze",
        item_id=item_id,
        schedule_id=schedule_id,
        date=today,
        km=km_now,
        until_km=body.until_km,
        until_date=body.until_date,
        note=body.note,
        created_at=datetime.now(UTC).isoformat(),
    )
    store.put_event(event)
    return event


@api.post("/items/{item_id}/schedules/{schedule_id}/baseline")
def set_baseline(
    item_id: str,
    schedule_id: str,
    body: BaselineIn,
    snapshot: Snapshot = Depends(require_snapshot),
    store: Store = Depends(get_store),
    today: date = Depends(get_today),
) -> Item:
    """Tell a schedule when it was last done, or start counting from today."""
    item, schedule = _find_schedule(snapshot, item_id, schedule_id)
    if not (schedule.type == "interval" and schedule.anchor == "actual"):
        raise HTTPException(400, "Só agendas por intervalo têm 'última vez'.")
    km_now = current_km(snapshot)
    if body.today:
        km, when = km_now, today
    else:
        km, when = body.km, body.date
        if km is None and when is None:
            raise HTTPException(422, "Informe o km ou a data da última vez.")
        if when is not None and when > today:
            raise HTTPException(422, "A data não pode ser no futuro.")
        if km is not None and km > km_now:
            raise HTTPException(
                422, f"O km não pode ser maior que o km atual ({fmt_km(km_now)})."
            )
    try:
        updated = Schedule(**{**schedule.model_dump(), "baseline_km": km, "baseline_date": when})
    except ValidationError as exc:
        raise HTTPException(422, _clean(exc.errors()[0]["msg"])) from exc
    item = item.model_copy(
        update={"schedules": [updated if s.id == schedule_id else s for s in item.schedules]}
    )
    store.put_item(item)
    return item


@api.delete("/events/{event_id}", status_code=204)
def delete_event(
    event_id: str,
    snapshot: Snapshot = Depends(require_snapshot),
    store: Store = Depends(get_store),
) -> None:
    """Undo a skip or a snooze."""
    _find(snapshot.events, event_id, "Evento")
    store.delete_event(event_id)


# --- Fuel ------------------------------------------------------------------


@api.get("/fuel")
def list_fuel(snapshot: Snapshot = Depends(require_snapshot)) -> list[FuelLog]:
    return snapshot.fuel


@api.post("/fuel", status_code=201)
def create_fuel(
    body: FuelLogIn,
    snapshot: Snapshot = Depends(require_snapshot),
    store: Store = Depends(get_store),
    today: date = Depends(get_today),
) -> FuelLog:
    _validate_entry(snapshot, body.date, body.km, today)
    log = FuelLog(id=new_id(), **body.model_dump())
    store.put_fuel(log)
    return log


@api.put("/fuel/{log_id}")
def update_fuel(
    log_id: str,
    body: FuelLogIn,
    snapshot: Snapshot = Depends(require_snapshot),
    store: Store = Depends(get_store),
    today: date = Depends(get_today),
) -> FuelLog:
    _find(snapshot.fuel, log_id, "Abastecimento")
    _validate_entry(snapshot, body.date, body.km, today, exclude_id=log_id)
    log = FuelLog(id=log_id, **body.model_dump())
    store.put_fuel(log)
    return log


@api.delete("/fuel/{log_id}", status_code=204)
def delete_fuel(
    log_id: str,
    snapshot: Snapshot = Depends(require_snapshot),
    store: Store = Depends(get_store),
) -> None:
    _find(snapshot.fuel, log_id, "Abastecimento")
    store.delete_fuel(log_id)


# --- Odometer --------------------------------------------------------------


@api.get("/odometer")
def list_odometer(snapshot: Snapshot = Depends(require_snapshot)) -> list[OdometerReading]:
    return snapshot.odometer


@api.post("/odometer", status_code=201)
def create_odometer(
    body: OdometerIn,
    snapshot: Snapshot = Depends(require_snapshot),
    store: Store = Depends(get_store),
    today: date = Depends(get_today),
) -> OdometerReading:
    _validate_entry(snapshot, body.date, body.km, today)
    reading = OdometerReading(id=new_id(), **body.model_dump())
    store.put_odometer(reading)
    return reading


@api.put("/odometer/{reading_id}")
def update_odometer(
    reading_id: str,
    body: OdometerIn,
    snapshot: Snapshot = Depends(require_snapshot),
    store: Store = Depends(get_store),
    today: date = Depends(get_today),
) -> OdometerReading:
    _find(snapshot.odometer, reading_id, "Leitura")
    _validate_entry(snapshot, body.date, body.km, today, exclude_id=reading_id)
    reading = OdometerReading(id=reading_id, **body.model_dump())
    store.put_odometer(reading)
    return reading


@api.delete("/odometer/{reading_id}", status_code=204)
def delete_odometer(
    reading_id: str,
    snapshot: Snapshot = Depends(require_snapshot),
    store: Store = Depends(get_store),
) -> None:
    _find(snapshot.odometer, reading_id, "Leitura")
    store.delete_odometer(reading_id)


# --- Maintenance -----------------------------------------------------------


@api.get("/maintenance")
def list_maintenance(snapshot: Snapshot = Depends(require_snapshot)) -> list[MaintenanceRecord]:
    return snapshot.maintenance


@api.post("/maintenance", status_code=201)
def create_maintenance(
    body: MaintenanceIn,
    snapshot: Snapshot = Depends(require_snapshot),
    store: Store = Depends(get_store),
    today: date = Depends(get_today),
) -> MaintenanceRecord:
    _check_items_exist(snapshot, body.item_ids)
    _validate_entry(snapshot, body.date, body.km, today)
    record = MaintenanceRecord(id=new_id(), **body.model_dump())
    store.put_maintenance(record)
    return record


@api.put("/maintenance/{record_id}")
def update_maintenance(
    record_id: str,
    body: MaintenanceIn,
    snapshot: Snapshot = Depends(require_snapshot),
    store: Store = Depends(get_store),
    today: date = Depends(get_today),
) -> MaintenanceRecord:
    _find(snapshot.maintenance, record_id, "Manutenção")
    _check_items_exist(snapshot, body.item_ids)
    _validate_entry(snapshot, body.date, body.km, today, exclude_id=record_id)
    record = MaintenanceRecord(id=record_id, **body.model_dump())
    store.put_maintenance(record)
    return record


@api.delete("/maintenance/{record_id}", status_code=204)
def delete_maintenance(
    record_id: str,
    snapshot: Snapshot = Depends(require_snapshot),
    store: Store = Depends(get_store),
) -> None:
    _find(snapshot.maintenance, record_id, "Manutenção")
    store.delete_maintenance(record_id)


# --- History and export ----------------------------------------------------


@api.get("/history")
def get_history(snapshot: Snapshot = Depends(require_snapshot)) -> list[HistoryEntry]:
    """Maintenance records, skips and snoozes merged, newest first."""
    names = {i.id: i.name for i in snapshot.items}
    entries = [
        HistoryEntry(
            kind="maintenance",
            id=m.id,
            date=m.date,
            km=m.km,
            item_ids=m.item_ids,
            item_names=[names.get(i, "(item removido)") for i in m.item_ids],
            cost_total=m.cost_total,
            shop=m.shop,
            notes=m.notes,
        )
        for m in snapshot.maintenance
    ]
    entries += [
        HistoryEntry(
            kind=e.type,
            id=e.id,
            date=e.date,
            km=e.km,
            item_ids=[e.item_id],
            item_names=[names.get(e.item_id, "(item removido)")],
            notes=e.note,
            until_km=e.until_km,
            until_date=e.until_date,
        )
        for e in snapshot.events
    ]
    entries.sort(key=lambda e: (e.date, e.km), reverse=True)
    return entries


@api.get("/export")
def export_all(snapshot: Snapshot = Depends(require_snapshot)) -> dict:
    return {
        "exported_at": datetime.now(UTC).isoformat(),
        "car": snapshot.car.model_dump(mode="json"),
        "items": [i.model_dump(mode="json") for i in snapshot.items],
        "fuel": [f.model_dump(mode="json") for f in snapshot.fuel],
        "odometer": [o.model_dump(mode="json") for o in snapshot.odometer],
        "maintenance": [m.model_dump(mode="json") for m in snapshot.maintenance],
        "events": [e.model_dump(mode="json") for e in snapshot.events],
    }


# --- Development seed ------------------------------------------------------


@api.post("/dev/seed")
def dev_seed(
    demo: bool = False, store: Store = Depends(get_store), today: date = Depends(get_today)
) -> dict:
    """Wipe the car and load the Prius seed. Local development only."""
    if os.environ.get("ENABLE_DEV_SEED") != "1":
        raise HTTPException(404, "Not Found")
    store.wipe()
    items = [
        Item(
            id=new_id(),
            name=body.name,
            jp_term=body.jp_term,
            notes=body.notes,
            schedules=_build_schedules(body, today, None),
        )
        for body in seed_data.seed_items()
    ]
    for item in items:
        store.put_item(item)
    fuel_count = maintenance_count = 0
    start_date = today
    if demo:
        ids = {i.name: i.id for i in items}
        start_date, fuel, maintenance = seed_data.demo_history(today, ids)
        for log in fuel:
            store.put_fuel(FuelLog(id=new_id(), **log.model_dump()))
        for record in maintenance:
            store.put_maintenance(MaintenanceRecord(id=new_id(), **record.model_dump()))
        fuel_count, maintenance_count = len(fuel), len(maintenance)
    store.put_car(seed_data.seed_car(start_date))
    return {"items": len(items), "fuel": fuel_count, "maintenance": maintenance_count}


app.include_router(api)
