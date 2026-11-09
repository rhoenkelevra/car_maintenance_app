"""Snooze replaces the due point of the current cycle; a completion spends it."""

from datetime import date

import pytest

from .helpers import item, maint, odo, sched, skip, snap, snooze, status_of, trigger

DONE = date(2026, 1, 10)
SNOOZED_ON = date(2026, 9, 1)


def oil(current_km, events=(), maintenance=(), today=date(2026, 9, 2), **schedule):
    """Oil every 7,500 km, done at 93,000 km (due at 100,500)."""
    schedule.setdefault("every_km", 7_500)
    return status_of(
        snap(
            [item(sched(**schedule))],
            maintenance=[maint(DONE, 93_000), *maintenance],
            odometer=[odo(SNOOZED_ON, current_km)],
            events=events,
        ),
        today,
    )


class TestSnooze:
    def test_without_snooze_it_is_due(self):
        status = oil(100_600)
        assert (status.status, status.snoozed) == ("due", False)

    def test_snooze_to_a_km_replaces_the_due_point(self):
        status = oil(100_600, events=[snooze(SNOOZED_ON, 100_600, until_km=105_000)])
        assert status.status == "ok"
        assert status.raw_status == "due"
        assert status.snoozed is True
        assert status.snooze_until_km == 105_000
        assert trigger(status, "km").due_km == 105_000

    @pytest.mark.parametrize(
        "current_km, expected",
        [
            (104_249, "ok"),
            (104_250, "upcoming"),
            (105_000, "due"),
            (105_749, "due"),
            (105_750, "overdue"),
        ],
    )
    def test_thresholds_apply_to_the_new_point(self, current_km, expected):
        events = [snooze(SNOOZED_ON, 100_600, until_km=105_000)]
        assert oil(current_km, events=events).status == expected

    def test_snooze_to_a_date_drops_the_other_triggers(self):
        events = [snooze(SNOOZED_ON, 100_600, until_date=date(2026, 12, 1))]
        status = oil(120_000, events=events, every_months=6)
        assert [t.kind for t in status.triggers] == ["date"]
        assert status.status == "ok"
        assert status.snooze_until_date == date(2026, 12, 1)

    def test_snooze_to_km_and_date_uses_whichever_comes_first(self):
        events = [snooze(SNOOZED_ON, 100_600, until_km=105_000, until_date=date(2026, 10, 1))]
        status = oil(100_700, events=events, today=date(2026, 10, 1))
        assert status.status == "due"
        assert status.driving == "date"

    def test_latest_snooze_wins(self):
        events = [
            snooze(SNOOZED_ON, 100_600, until_km=102_000),
            snooze(date(2026, 9, 20), 101_900, until_km=106_000),
        ]
        assert trigger(oil(101_900, events=events), "km").due_km == 106_000

    def test_work_after_the_snooze_spends_it(self):
        events = [snooze(SNOOZED_ON, 100_600, until_km=105_000)]
        status = oil(104_000, events=events, maintenance=[maint(date(2026, 10, 5), 104_000)])
        assert status.snoozed is False
        assert trigger(status, "km").due_km == 111_500

    def test_work_on_the_same_day_as_the_snooze_spends_it(self):
        events = [snooze(SNOOZED_ON, 100_600, until_km=105_000)]
        status = oil(100_600, events=events, maintenance=[maint(SNOOZED_ON, 100_600)])
        assert status.snoozed is False
        assert trigger(status, "km").due_km == 108_100

    def test_skip_after_the_snooze_spends_it(self):
        events = [
            snooze(SNOOZED_ON, 100_600, until_km=105_000),
            skip(date(2026, 9, 10), 101_000),
        ]
        status = oil(101_000, events=events)
        assert status.snoozed is False
        assert trigger(status, "km").due_km == 108_500

    def test_snooze_of_another_schedule_is_ignored(self):
        events = [snooze(SNOOZED_ON, 100_600, until_km=105_000, schedule_id="other")]
        assert oil(100_600, events=events).snoozed is False


class TestSnoozeOnFixedSchedule:
    """車検 due 2027-03-20, snoozed on 2027-03-25 until 2027-04-10."""

    def snapshot(self, maintenance=()):
        s = sched(anchor="fixed", every_months=24, first_due_date=date(2027, 3, 20))
        return snap(
            [item(s)],
            maintenance=maintenance,
            events=[snooze(date(2027, 3, 25), 96_000, until_date=date(2027, 4, 10))],
        )

    def test_snooze_moves_the_due_date(self):
        status = status_of(self.snapshot(), date(2027, 3, 26))
        assert status.raw_status == "due"
        assert status.snoozed is True
        assert trigger(status, "date").due_date == date(2027, 4, 10)
        assert status.status == "upcoming"  # inside the 72-day lead of the new date

    def test_it_comes_back_as_due_on_the_new_date(self):
        assert status_of(self.snapshot(), date(2027, 4, 10)).status == "due"

    def test_work_clears_the_date_and_the_snooze(self):
        done = self.snapshot(maintenance=[maint(date(2027, 4, 5), 96_500)])
        status = status_of(done, date(2027, 4, 6))
        assert status.snoozed is False
        assert status.status == "ok"
        assert trigger(status, "date").due_date == date(2029, 3, 20)
