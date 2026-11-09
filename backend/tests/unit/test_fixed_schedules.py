"""Schedules with fixed due points: fixed-grid intervals, yearly pinned, one-time."""

from datetime import date

import pytest

from .helpers import TODAY, car, item, maint, odo, sched, skip, snap, status_of, trigger


def shaken():
    """車検: every 24 months on fixed dates, first due 2027-03-20 (lead 72 days)."""
    return sched(anchor="fixed", every_months=24, first_due_date=date(2027, 3, 20))


class TestFixedDateGrid:
    @pytest.mark.parametrize(
        "today, expected",
        [
            (date(2026, 11, 9), "ok"),
            (date(2027, 1, 6), "ok"),
            (date(2027, 1, 7), "upcoming"),  # 72 days before
            (date(2027, 3, 19), "upcoming"),
            (date(2027, 3, 20), "due"),
            (date(2027, 5, 30), "due"),
            (date(2027, 5, 31), "overdue"),  # 72 days after
        ],
    )
    def test_colour_boundaries(self, today, expected):
        assert status_of(snap([item(shaken())]), today).status == expected

    def test_needs_no_baseline(self):
        status = status_of(snap([item(shaken())]))
        assert status.status == "ok"
        assert trigger(status, "date").due_date == date(2027, 3, 20)

    def test_work_inside_the_window_moves_to_the_next_grid_date(self):
        snapshot = snap([item(shaken())], maintenance=[maint(date(2027, 2, 10), 96_000)])
        status = status_of(snapshot, date(2027, 2, 11))
        assert status.status == "ok"
        assert trigger(status, "date").due_date == date(2029, 3, 20)

    def test_work_exactly_at_the_yellow_threshold_clears_it(self):
        snapshot = snap([item(shaken())], maintenance=[maint(date(2027, 1, 7), 96_000)])
        assert trigger(status_of(snapshot, date(2027, 1, 8)), "date").due_date == date(2029, 3, 20)

    def test_work_before_the_window_does_not_clear_it(self):
        snapshot = snap([item(shaken())], maintenance=[maint(date(2026, 12, 1), 94_000)])
        status = status_of(snapshot, date(2027, 1, 7))
        assert status.status == "upcoming"
        assert trigger(status, "date").due_date == date(2027, 3, 20)

    def test_late_work_keeps_the_grid(self):
        # Done three months late: the next one is still 2029-03-20, not 2029-06-15.
        snapshot = snap([item(shaken())], maintenance=[maint(date(2027, 6, 15), 97_000)])
        assert trigger(status_of(snapshot, date(2027, 6, 16)), "date").due_date == date(2029, 3, 20)

    def test_one_late_record_clears_every_missed_date(self):
        snapshot = snap([item(shaken())], maintenance=[maint(date(2029, 4, 1), 110_000)])
        assert trigger(status_of(snapshot, date(2029, 4, 2)), "date").due_date == date(2031, 3, 20)

    def test_never_done_stays_on_the_first_missed_date(self):
        status = status_of(snap([item(shaken())]), date(2029, 4, 1))
        assert status.status == "overdue"
        assert trigger(status, "date").due_date == date(2027, 3, 20)

    def test_skip_clears_the_pending_date(self):
        snapshot = snap([item(shaken())], events=[skip(date(2027, 3, 25), 96_000)])
        assert trigger(status_of(snapshot, date(2027, 3, 26)), "date").due_date == date(2029, 3, 20)

    def test_reports_last_done(self):
        snapshot = snap([item(shaken())], maintenance=[maint(date(2027, 2, 10), 96_000)])
        status = status_of(snapshot, date(2027, 2, 11))
        assert (status.last_done_date, status.last_done_km) == (date(2027, 2, 10), 96_000)


class TestFixedKmGrid:
    """Every 100,000 km on the grid 100,000 / 200,000 / ... (lead 10,000 km)."""

    def schedule(self):
        return sched(anchor="fixed", every_km=100_000, first_due_km=100_000)

    def test_first_due_point(self):
        status = status_of(snap([item(self.schedule())]))  # car at 93,000
        assert status.status == "upcoming"
        t = trigger(status, "km")
        assert (t.due_km, t.remaining) == (100_000, 7_000)

    def test_work_from_the_yellow_threshold_moves_to_the_next_point(self):
        snapshot = snap([item(self.schedule())], maintenance=[maint(TODAY, 95_000)])
        status = status_of(snapshot)
        assert status.status == "ok"
        assert trigger(status, "km").due_km == 200_000

    def test_work_before_the_yellow_threshold_does_not_clear(self):
        snapshot = snap(
            [item(self.schedule())],
            maintenance=[maint(date(2025, 6, 1), 80_000)],
            car_=car(start_km=70_000, start_date=date(2025, 1, 1)),
            odometer=[odo(TODAY, 93_000)],
        )
        assert trigger(status_of(snapshot), "km").due_km == 100_000

    def test_grid_with_km_and_date_uses_whichever_comes_first(self):
        s = sched(
            anchor="fixed",
            every_km=10_000,
            first_due_km=100_000,
            every_months=12,
            first_due_date=date(2026, 12, 1),
        )
        status = status_of(snap([item(s)]), date(2026, 12, 1))
        assert status.status == "due"
        assert status.driving == "date"
        assert trigger(status, "km").status == "ok"


class TestYearlyPinned:
    """自動車税 every May 31, created on 2026-11-09 (lead and margin 36 days)."""

    def tax(self, **kwargs):
        kwargs.setdefault("months", [5])
        kwargs.setdefault("day", 31)
        kwargs.setdefault("created_on", date(2026, 11, 9))
        return sched(type="yearly", **kwargs)

    @pytest.mark.parametrize(
        "today, expected",
        [
            (date(2026, 11, 9), "ok"),
            (date(2027, 4, 24), "ok"),
            (date(2027, 4, 25), "upcoming"),
            (date(2027, 5, 31), "due"),
            (date(2027, 7, 5), "due"),
            (date(2027, 7, 6), "overdue"),
        ],
    )
    def test_colour_boundaries(self, today, expected):
        status = status_of(snap([item(self.tax())]), today)
        assert status.status == expected
        assert trigger(status, "date").due_date == date(2027, 5, 31)

    @pytest.mark.parametrize(
        "created, first_due",
        [
            (date(2026, 5, 20), date(2026, 5, 31)),  # this year's date is still ahead
            (date(2026, 5, 31), date(2026, 5, 31)),
            (date(2026, 6, 1), date(2027, 5, 31)),  # already passed: next year
        ],
    )
    def test_first_due_date_follows_the_creation_date(self, created, first_due):
        status = status_of(snap([item(self.tax(created_on=created))]), created)
        assert trigger(status, "date").due_date == first_due

    def test_work_inside_the_window_moves_to_next_year(self):
        snapshot = snap([item(self.tax())], maintenance=[maint(date(2027, 4, 28), 96_000)])
        assert trigger(status_of(snapshot, date(2027, 4, 29)), "date").due_date == date(2028, 5, 31)

    def test_work_before_the_window_does_not_clear_it(self):
        snapshot = snap([item(self.tax())], maintenance=[maint(date(2027, 3, 1), 95_000)])
        assert trigger(status_of(snapshot, date(2027, 4, 25)), "date").due_date == date(2027, 5, 31)

    def test_several_months_in_one_schedule(self):
        # Tyre swap every May 1 and November 1 (lead 18 days).
        s = self.tax(months=[5, 11], day=1, created_on=date(2026, 6, 15))
        assert trigger(status_of(snap([item(s)]), date(2026, 6, 15)), "date").due_date == date(
            2026, 11, 1
        )
        done = snap([item(s)], maintenance=[maint(date(2026, 10, 20), 95_000)])
        assert trigger(status_of(done, date(2026, 10, 21)), "date").due_date == date(2027, 5, 1)

    def test_day_is_clamped_to_the_month_length(self):
        s = self.tax(months=[2], day=31, created_on=date(2026, 1, 1))
        assert trigger(status_of(snap([item(s)]), date(2026, 1, 1)), "date").due_date == date(
            2026, 2, 28
        )
        leap = self.tax(months=[2], day=31, created_on=date(2028, 1, 1))
        assert trigger(status_of(snap([item(leap)]), date(2028, 1, 1)), "date").due_date == date(
            2028, 2, 29
        )


class TestOneTime:
    """Spark plugs once at 100,000 km (lead and margin 500 km)."""

    def by_km(self, current_km, maintenance=()):
        s = sched(type="one_time", at_km=100_000)
        return status_of(
            snap([item(s)], odometer=[odo(TODAY, current_km)], maintenance=maintenance)
        )

    @pytest.mark.parametrize(
        "current_km, expected",
        [
            (93_000, "ok"),
            (99_499, "ok"),
            (99_500, "upcoming"),
            (100_000, "due"),
            (100_499, "due"),
            (100_500, "overdue"),
        ],
    )
    def test_km_boundaries(self, current_km, expected):
        assert self.by_km(current_km).status == expected

    @pytest.mark.parametrize(
        "today, expected",
        [
            (date(2026, 12, 15), "ok"),
            (date(2026, 12, 16), "upcoming"),  # 30 days before
            (date(2027, 1, 15), "due"),
            (date(2027, 2, 13), "due"),
            (date(2027, 2, 14), "overdue"),  # 30 days after
        ],
    )
    def test_date_boundaries(self, today, expected):
        s = sched(type="one_time", on_date=date(2027, 1, 15))
        assert status_of(snap([item(s)]), today).status == expected

    def test_km_or_date_whichever_comes_first(self):
        s = sched(type="one_time", at_km=100_000, on_date=date(2027, 1, 15))
        status = status_of(snap([item(s)]), date(2027, 1, 15))  # car at 93,000
        assert status.status == "due"
        assert status.driving == "date"

    def test_early_work_does_not_finish_it(self):
        # An oil change at 94,000 km must not clear "oil at 100,000 km".
        status = self.by_km(94_000, maintenance=[maint(TODAY, 94_000)])
        assert status.status == "ok"
        assert trigger(status, "km").due_km == 100_000

    def test_work_from_the_yellow_threshold_finishes_it(self):
        status = self.by_km(99_600, maintenance=[maint(TODAY, 99_600)])
        assert status.status == "done"
        assert status.raw_status == "done"
        assert status.triggers == []
        assert status.last_done_km == 99_600

    def test_interval_and_one_time_on_the_same_item(self):
        every = sched(id="s1", every_km=7_500)
        once = sched(id="s2", type="one_time", at_km=100_000)
        early = snap([item(every, once)], maintenance=[maint(TODAY, 94_000)])
        assert trigger(status_of(early, schedule_id="s1"), "km").due_km == 101_500
        assert status_of(early, schedule_id="s2").status == "ok"

        at_mark = snap([item(every, once)], maintenance=[maint(TODAY, 99_800)])
        assert trigger(status_of(at_mark, schedule_id="s1"), "km").due_km == 107_300
        assert status_of(at_mark, schedule_id="s2").status == "done"
