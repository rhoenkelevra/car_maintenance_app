from datetime import date

import pytest
from pydantic import ValidationError

from app.models import Car, FuelLogIn, MaintenanceIn, ScheduleIn, SnoozeIn


def invalid(**kwargs) -> str:
    with pytest.raises(ValidationError) as exc:
        ScheduleIn(**kwargs)
    return exc.value.errors()[0]["msg"]


class TestIntervalSchedule:
    def test_needs_at_least_one_interval(self):
        assert "ao menos um intervalo" in invalid(type="interval")

    @pytest.mark.parametrize(
        "kwargs", [{"every_km": 7_500}, {"every_months": 6}, {"every_fillups": 3}]
    )
    def test_any_single_interval_is_enough(self, kwargs):
        assert ScheduleIn(type="interval", **kwargs).anchor == "actual"

    @pytest.mark.parametrize("field", ["every_km", "every_months", "every_fillups"])
    def test_intervals_must_be_positive(self, field):
        with pytest.raises(ValidationError):
            ScheduleIn(type="interval", **{field: 0})

    def test_fixed_km_needs_a_first_due_km(self):
        assert "primeiro vencimento" in invalid(type="interval", anchor="fixed", every_km=10_000)

    def test_fixed_months_needs_a_first_due_date(self):
        assert "primeiro vencimento" in invalid(type="interval", anchor="fixed", every_months=24)

    def test_fixed_rejects_fillups(self):
        message = invalid(
            type="interval", anchor="fixed", every_fillups=3, first_due_date=date(2027, 1, 1)
        )
        assert "abastecimentos" in message

    def test_fixed_with_first_due_is_valid(self):
        s = ScheduleIn(
            type="interval", anchor="fixed", every_months=24, first_due_date=date(2027, 3, 20)
        )
        assert s.first_due_date == date(2027, 3, 20)

    def test_baseline_needs_km_when_there_is_a_km_interval(self):
        message = invalid(type="interval", every_km=7_500, baseline_date=date(2026, 1, 1))
        assert "km da última vez" in message

    def test_baseline_needs_a_date_when_there_is_a_month_interval(self):
        assert "data da última vez" in invalid(type="interval", every_months=6, baseline_km=90_000)

    def test_baseline_needs_a_date_when_there_is_a_fillup_interval(self):
        assert "data da última vez" in invalid(type="interval", every_fillups=3, baseline_km=90_000)

    def test_km_only_schedule_accepts_a_km_only_baseline(self):
        assert ScheduleIn(type="interval", every_km=100_000, baseline_km=0).baseline_km == 0

    def test_no_baseline_at_all_is_valid(self):
        s = ScheduleIn(type="interval", every_km=7_500, every_months=6)
        assert s.baseline_km is None and s.baseline_date is None


class TestYearlySchedule:
    def test_needs_a_month(self):
        assert "ao menos um mês" in invalid(type="yearly")

    @pytest.mark.parametrize("month", [0, 13, -1])
    def test_rejects_invalid_months(self, month):
        assert "Mês inválido" in invalid(type="yearly", months=[month])

    def test_months_are_sorted_and_deduplicated(self):
        assert ScheduleIn(type="yearly", months=[11, 5, 11]).months == [5, 11]

    @pytest.mark.parametrize("day", [0, 32])
    def test_day_must_be_a_calendar_day(self, day):
        with pytest.raises(ValidationError):
            ScheduleIn(type="yearly", months=[5], day=day)


class TestOneTimeSchedule:
    def test_needs_a_km_or_a_date(self):
        assert "evento único" in invalid(type="one_time")

    def test_km_alone_or_date_alone_is_enough(self):
        assert ScheduleIn(type="one_time", at_km=100_000).at_km == 100_000
        assert ScheduleIn(type="one_time", on_date=date(2027, 1, 1)).on_date == date(2027, 1, 1)


class TestOtherModels:
    def test_snooze_needs_a_target(self):
        with pytest.raises(ValidationError):
            SnoozeIn()

    def test_maintenance_needs_at_least_one_item(self):
        with pytest.raises(ValidationError):
            MaintenanceIn(date=date(2026, 1, 1), km=93_000, item_ids=[])

    def test_fuel_log_defaults(self):
        log = FuelLogIn(date=date(2026, 1, 1), km=93_000)
        assert (log.fuel_type, log.full_tank, log.litres, log.price_total) == (
            "regular",
            True,
            None,
            None,
        )

    def test_fuel_log_rejects_negative_km_and_zero_litres(self):
        with pytest.raises(ValidationError):
            FuelLogIn(date=date(2026, 1, 1), km=-1)
        with pytest.raises(ValidationError):
            FuelLogIn(date=date(2026, 1, 1), km=93_000, litres=0)

    def test_car_needs_maker_model_start_km_and_start_date(self):
        with pytest.raises(ValidationError):
            Car(maker="", model="Prius", start_km=0, start_date=date(2026, 1, 1))
        with pytest.raises(ValidationError):
            Car(maker="Toyota", model="Prius", start_km=-5, start_date=date(2026, 1, 1))
