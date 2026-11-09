"""Data models shared by the API, the storage layer and the status engine."""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, model_validator

ScheduleType = Literal["interval", "yearly", "one_time"]
Anchor = Literal["actual", "fixed"]
Status = Literal["ok", "upcoming", "due", "overdue", "no_history", "done"]
TriggerKind = Literal["km", "date", "fillups"]

# Alias for models whose `date` field has a default: inside such a class body
# the field name would otherwise shadow the type.
Date = date


# --- Car -------------------------------------------------------------------


class Car(BaseModel):
    maker: str = Field(min_length=1)
    model: str = Field(min_length=1)
    model_code: str = ""
    year: int | None = Field(None, ge=1900, le=2100)
    plate: str = ""
    tank_l: float | None = Field(None, gt=0)
    start_km: int = Field(ge=0)
    start_date: date
    shaken_expiry: date | None = None
    notes: str = ""


# --- Items and schedules ---------------------------------------------------


class ScheduleIn(BaseModel):
    """A rule saying when an item is due. `id` is omitted for new schedules."""

    id: str | None = None
    type: ScheduleType
    anchor: Anchor = "actual"

    # interval
    every_km: int | None = Field(None, gt=0)
    every_months: int | None = Field(None, gt=0)
    every_fillups: int | None = Field(None, gt=0)
    # interval with a fixed anchor: the first due point of the grid
    first_due_km: int | None = Field(None, ge=0)
    first_due_date: date | None = None
    # interval with an actual anchor: manual "last done" baseline
    baseline_km: int | None = Field(None, ge=0)
    baseline_date: date | None = None

    # yearly pinned
    months: list[int] = Field(default_factory=list)
    day: int = Field(1, ge=1, le=31)

    # one-time
    at_km: int | None = Field(None, ge=0)
    on_date: date | None = None

    # threshold overrides (default: 10% of the interval)
    lead_km: int | None = Field(None, ge=0)
    lead_days: int | None = Field(None, ge=0)
    overdue_km: int | None = Field(None, ge=0)
    overdue_days: int | None = Field(None, ge=0)

    active: bool = True
    created_on: date | None = None

    @model_validator(mode="after")
    def _check_shape(self) -> "ScheduleIn":
        if self.type == "interval":
            if not (self.every_km or self.every_months or self.every_fillups):
                raise ValueError("Informe ao menos um intervalo: km, meses ou abastecimentos.")
            if self.anchor == "fixed":
                if self.every_fillups:
                    raise ValueError("Agenda de data fixa não aceita intervalo por abastecimentos.")
                if self.every_km and self.first_due_km is None:
                    raise ValueError("Informe o km do primeiro vencimento.")
                if self.every_months and self.first_due_date is None:
                    raise ValueError("Informe a data do primeiro vencimento.")
            elif self.baseline_km is not None or self.baseline_date is not None:
                if self.every_km and self.baseline_km is None:
                    raise ValueError("Informe o km da última vez.")
                if (self.every_months or self.every_fillups) and self.baseline_date is None:
                    raise ValueError("Informe a data da última vez.")
        elif self.type == "yearly":
            if not self.months:
                raise ValueError("Escolha ao menos um mês.")
            if any(m < 1 or m > 12 for m in self.months):
                raise ValueError("Mês inválido.")
            self.months = sorted(set(self.months))
        elif self.type == "one_time":
            if self.at_km is None and self.on_date is None:
                raise ValueError("Informe o km ou a data do evento único.")
        return self


class Schedule(ScheduleIn):
    id: str
    created_on: date


class ItemIn(BaseModel):
    name: str = Field(min_length=1)
    jp_term: str = ""
    notes: str = ""
    schedules: list[ScheduleIn] = Field(default_factory=list)


class Item(BaseModel):
    id: str
    name: str
    jp_term: str = ""
    notes: str = ""
    archived: bool = False
    schedules: list[Schedule] = Field(default_factory=list)


# --- Logs ------------------------------------------------------------------


class FuelLogIn(BaseModel):
    date: date
    km: int = Field(ge=0)
    litres: float | None = Field(None, gt=0)
    price_total: int | None = Field(None, ge=0)
    full_tank: bool = True
    fuel_type: str = "regular"
    station: str = ""
    notes: str = ""


class FuelLog(FuelLogIn):
    id: str


class OdometerIn(BaseModel):
    date: date
    km: int = Field(ge=0)
    note: str = ""


class OdometerReading(OdometerIn):
    id: str


class MaintenanceIn(BaseModel):
    date: date
    km: int = Field(ge=0)
    item_ids: list[str] = Field(min_length=1)
    cost_total: int | None = Field(None, ge=0)
    shop: str = ""
    notes: str = ""


class MaintenanceRecord(MaintenanceIn):
    id: str


class ScheduleEvent(BaseModel):
    """A skip or a snooze on one schedule."""

    id: str
    type: Literal["skip", "snooze"]
    item_id: str
    schedule_id: str
    date: date
    km: int
    until_km: int | None = None
    until_date: date | None = None
    note: str = ""
    created_at: str = ""


# --- Request bodies for schedule actions ------------------------------------


class SkipIn(BaseModel):
    note: str = ""


class SnoozeIn(BaseModel):
    until_km: int | None = Field(None, ge=0)
    until_date: date | None = None
    note: str = ""

    @model_validator(mode="after")
    def _check(self) -> "SnoozeIn":
        if self.until_km is None and self.until_date is None:
            raise ValueError("Informe até que km ou data adiar.")
        return self


class BaselineIn(BaseModel):
    today: bool = False
    km: int | None = Field(None, ge=0)
    date: Date | None = None


# --- Engine output ---------------------------------------------------------


class TriggerStatus(BaseModel):
    kind: TriggerKind
    status: Status
    # km, days or fill-ups left until due; negative once past due
    remaining: int
    due_km: int | None = None
    due_date: date | None = None
    due_fillups: int | None = None
    # km triggers only: when the due km is expected at the current pace
    projected_date: date | None = None


class ScheduleStatus(BaseModel):
    item_id: str
    item_name: str
    jp_term: str
    schedule_id: str
    schedule_type: ScheduleType
    status: Status
    # status ignoring any snooze
    raw_status: Status
    triggers: list[TriggerStatus] = Field(default_factory=list)
    driving: TriggerKind | None = None
    estimated_due_date: date | None = None
    snoozed: bool = False
    snooze_until_km: int | None = None
    snooze_until_date: date | None = None
    last_done_date: date | None = None
    last_done_km: int | None = None


class Dashboard(BaseModel):
    today: date
    current_km: int
    last_reading_date: date
    estimated_km: int | None = None
    pace_km_per_day: float | None = None
    stale: bool = False
    notifications: list[ScheduleStatus] = Field(default_factory=list)
    statuses: list[ScheduleStatus] = Field(default_factory=list)


class HistoryEntry(BaseModel):
    kind: Literal["maintenance", "skip", "snooze"]
    id: str
    date: date
    km: int
    item_ids: list[str] = Field(default_factory=list)
    item_names: list[str] = Field(default_factory=list)
    cost_total: int | None = None
    shop: str = ""
    notes: str = ""
    until_km: int | None = None
    until_date: date | None = None
