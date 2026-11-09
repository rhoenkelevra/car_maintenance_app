"""Interval schedules that count from when the work was actually done."""

from datetime import date

import pytest

from .helpers import TODAY, fuel, item, maint, odo, sched, skip, snap, status_of, trigger

DONE = date(2026, 1, 10)


def oil_by_km(current_km: int, **overrides):
    """Oil every 7,500 km, last done at 93,000 km, odometer now at `current_km`."""
    s = sched(every_km=7_500, **overrides)
    return status_of(
        snap([item(s)], maintenance=[maint(DONE, 93_000)], odometer=[odo(TODAY, current_km)])
    )


class TestNoHistory:
    def test_schedule_without_baseline_is_grey(self):
        status = status_of(snap([item(sched(every_km=7_500, every_months=6))]))
        assert status.status == "no_history"
        assert status.raw_status == "no_history"
        assert status.triggers == []
        assert status.driving is None
        assert status.last_done_date is None

    def test_maintenance_of_another_item_does_not_give_history(self):
        other = item(sched(id="s2", every_km=5_000), id="i2", name="Rodízio")
        snapshot = snap([item(sched(every_km=7_500)), other], maintenance=[maint(DONE, 93_000, "i2")])
        assert status_of(snapshot).status == "no_history"
        assert status_of(snapshot, schedule_id="s2").status == "ok"


class TestKmTrigger:
    @pytest.mark.parametrize(
        "current_km, expected",
        [
            (93_000, "ok"),
            (99_749, "ok"),
            (99_750, "upcoming"),  # 750 km before due
            (100_499, "upcoming"),
            (100_500, "due"),
            (101_249, "due"),
            (101_250, "overdue"),  # 750 km past due
        ],
    )
    def test_colour_boundaries(self, current_km, expected):
        assert oil_by_km(current_km).status == expected

    def test_reports_due_km_and_remaining(self):
        t = trigger(oil_by_km(100_000), "km")
        assert (t.due_km, t.remaining) == (100_500, 500)

    def test_remaining_is_negative_once_past_due(self):
        assert trigger(oil_by_km(100_800), "km").remaining == -300

    def test_lead_override_shows_yellow_earlier(self):
        assert oil_by_km(98_500).status == "ok"
        assert oil_by_km(98_500, lead_km=2_000).status == "upcoming"

    def test_overdue_override(self):
        assert oil_by_km(100_600).status == "due"
        assert oil_by_km(100_600, overdue_km=100).status == "overdue"


class TestDateTrigger:
    """Every 6 months from 2026-01-10: due 2026-07-10, lead and margin 18 days."""

    @pytest.mark.parametrize(
        "today, expected",
        [
            (date(2026, 1, 10), "ok"),
            (date(2026, 6, 21), "ok"),
            (date(2026, 6, 22), "upcoming"),
            (date(2026, 7, 9), "upcoming"),
            (date(2026, 7, 10), "due"),
            (date(2026, 7, 27), "due"),
            (date(2026, 7, 28), "overdue"),
        ],
    )
    def test_colour_boundaries(self, today, expected):
        snapshot = snap([item(sched(every_months=6))], maintenance=[maint(DONE, 93_000)])
        assert status_of(snapshot, today).status == expected

    def test_reports_due_date_and_remaining_days(self):
        snapshot = snap([item(sched(every_months=6))], maintenance=[maint(DONE, 93_000)])
        t = trigger(status_of(snapshot, date(2026, 7, 1)), "date")
        assert (t.due_date, t.remaining) == (date(2026, 7, 10), 9)
        assert trigger(status_of(snapshot, date(2026, 7, 15)), "date").remaining == -5

    def test_month_end_baseline_clamps_the_due_date(self):
        snapshot = snap(
            [item(sched(every_months=6))], maintenance=[maint(date(2026, 8, 31), 93_000)]
        )
        assert trigger(status_of(snapshot), "date").due_date == date(2027, 2, 28)


class TestCombinedTriggers:
    """Oil every 7,500 km or 6 months: whichever comes first."""

    def snapshot(self, current_km):
        s = sched(every_km=7_500, every_months=6)
        return snap(
            [item(s)], maintenance=[maint(DONE, 93_000)], odometer=[odo(DONE, current_km)]
        )

    def test_time_fires_first_with_few_km(self):
        status = status_of(self.snapshot(94_000), date(2026, 7, 10))
        assert status.status == "due"
        assert status.driving == "date"
        assert trigger(status, "km").status == "ok"

    def test_km_fires_first_with_many_km(self):
        status = status_of(self.snapshot(101_300), date(2026, 2, 1))
        assert status.status == "overdue"
        assert status.driving == "km"
        assert trigger(status, "date").status == "ok"

    def test_ok_only_when_every_trigger_is_ok(self):
        status = status_of(self.snapshot(94_000), date(2026, 2, 1))
        assert status.status == "ok"
        assert {t.kind for t in status.triggers} == {"km", "date"}


class TestBaseline:
    def test_registering_early_restarts_the_cycle(self):
        s = sched(every_km=7_500)
        snapshot = snap(
            [item(s)], maintenance=[maint(DONE, 93_000), maint(date(2026, 3, 1), 95_000)]
        )
        status = status_of(snapshot)
        assert trigger(status, "km").due_km == 102_500
        assert (status.last_done_date, status.last_done_km) == (date(2026, 3, 1), 95_000)

    def test_late_work_counts_from_when_it_was_done(self):
        # Due at 100,500 but done at 100,900: next is 108,400, not 108,000.
        s = sched(every_km=7_500)
        snapshot = snap(
            [item(s)], maintenance=[maint(DONE, 93_000), maint(date(2026, 9, 1), 100_900)]
        )
        assert trigger(status_of(snapshot), "km").due_km == 108_400

    def test_manual_baseline_gives_history(self):
        s = sched(every_km=7_500, every_months=6, baseline_km=90_000, baseline_date=date(2025, 12, 1))
        status = status_of(snap([item(s)]))
        assert trigger(status, "km").due_km == 97_500
        assert trigger(status, "date").due_date == date(2026, 6, 1)

    def test_record_newer_than_manual_baseline_wins(self):
        s = sched(every_km=7_500, baseline_km=90_000, baseline_date=date(2025, 12, 1))
        snapshot = snap([item(s)], maintenance=[maint(DONE, 93_000)])
        assert trigger(status_of(snapshot), "km").due_km == 100_500

    def test_manual_baseline_newer_than_record_wins(self):
        s = sched(every_km=7_500, baseline_km=95_000, baseline_date=date(2026, 5, 1))
        snapshot = snap([item(s)], maintenance=[maint(DONE, 93_000)])
        assert trigger(status_of(snapshot), "km").due_km == 102_500

    def test_km_only_baseline_from_new(self):
        # e-CVT fluid: never changed, counts from 0 km, due at 100,000.
        s = sched(every_km=100_000, baseline_km=0)
        status = status_of(snap([item(s)]))  # car is at 93,000 km
        assert status.status == "upcoming"  # yellow from 90,000
        assert trigger(status, "km").remaining == 7_000
        assert status.last_done_km == 0

    def test_skip_counts_as_a_baseline(self):
        s = sched(every_km=7_500)
        snapshot = snap(
            [item(s)],
            maintenance=[maint(DONE, 93_000)],
            odometer=[odo(date(2026, 9, 1), 100_600)],
            events=[skip(date(2026, 9, 1), 100_600)],
        )
        status = status_of(snapshot)
        assert status.status == "ok"
        assert trigger(status, "km").due_km == 108_100

    def test_skip_does_not_touch_a_sibling_schedule(self):
        by_km = sched(id="s1", every_km=7_500)
        by_time = sched(id="s2", every_months=6)
        snapshot = snap(
            [item(by_km, by_time)],
            maintenance=[maint(DONE, 93_000)],
            events=[skip(date(2026, 7, 10), 93_000, schedule_id="s1")],
        )
        assert trigger(status_of(snapshot, schedule_id="s2"), "date").due_date == date(2026, 7, 10)

    def test_one_record_resets_every_schedule_of_the_item(self):
        by_km = sched(id="s1", every_km=7_500)
        by_time = sched(id="s2", every_months=6)
        snapshot = snap([item(by_km, by_time)], maintenance=[maint(DONE, 93_000)])
        assert status_of(snapshot, schedule_id="s1").last_done_km == 93_000
        assert status_of(snapshot, schedule_id="s2").last_done_date == DONE

    def test_one_record_can_cover_several_items(self):
        oil = item(sched(id="s1", every_km=7_500), id="i1")
        filt = item(sched(id="s2", every_km=7_500), id="i2", name="Filtro de óleo")
        snapshot = snap([oil, filt], maintenance=[maint(DONE, 93_000, "i1", "i2")])
        assert status_of(snapshot, schedule_id="s1").status == "ok"
        assert status_of(snapshot, schedule_id="s2").status == "ok"


class TestFillups:
    """Additive every 3 fill-ups, last put in on 2026-03-01 at 94,000 km."""

    BASE = date(2026, 3, 1)
    LOGS = [
        (date(2026, 3, 10), 94_300),
        (date(2026, 3, 20), 94_600),
        (date(2026, 3, 30), 94_900),
        (date(2026, 4, 10), 95_200),
    ]

    def status(self, logs, every=3):
        s = sched(every_fillups=every)
        return status_of(
            snap(
                [item(s)],
                maintenance=[maint(self.BASE, 94_000)],
                fuel=[fuel(d, km) for d, km in logs],
            )
        )

    @pytest.mark.parametrize(
        "count, expected", [(0, "ok"), (1, "ok"), (2, "upcoming"), (3, "due"), (4, "overdue")]
    )
    def test_colour_by_number_of_fillups(self, count, expected):
        status = self.status(self.LOGS[:count])
        assert status.status == expected
        t = trigger(status, "fillups")
        assert (t.due_fillups, t.remaining) == (3, 3 - count)

    def test_fillup_on_the_same_day_and_km_as_the_baseline_does_not_count(self):
        # The additive went into that very tank.
        assert trigger(self.status([(self.BASE, 94_000)]), "fillups").remaining == 3

    def test_later_fillup_on_the_same_day_counts(self):
        assert trigger(self.status([(self.BASE, 94_050)]), "fillups").remaining == 2

    def test_fillups_before_the_baseline_do_not_count(self):
        assert trigger(self.status([(date(2026, 2, 20), 93_800)]), "fillups").remaining == 3

    def test_partial_fillups_count(self):
        s = sched(every_fillups=3)
        logs = [fuel(d, km, full_tank=False) for d, km in self.LOGS[:3]]
        snapshot = snap([item(s)], maintenance=[maint(self.BASE, 94_000)], fuel=logs)
        assert status_of(snapshot).status == "due"

    def test_every_single_fillup(self):
        assert self.status([], every=1).status == "ok"
        assert self.status(self.LOGS[:1], every=1).status == "due"
        assert self.status(self.LOGS[:2], every=1).status == "overdue"

    def test_fillups_or_km_whichever_comes_first(self):
        s = sched(every_fillups=3, every_km=5_000)
        snapshot = snap(
            [item(s)],
            maintenance=[maint(self.BASE, 94_000)],
            fuel=[fuel(d, km) for d, km in self.LOGS[:3]],
        )
        status = status_of(snapshot)
        assert status.status == "due"
        assert status.driving == "fillups"
        assert trigger(status, "km").status == "ok"


class TestExclusions:
    def test_inactive_schedules_are_not_evaluated(self):
        from app.engine import evaluate_all

        s = sched(every_km=7_500, active=False)
        assert evaluate_all(snap([item(s)]), TODAY) == []

    def test_archived_items_are_not_evaluated(self):
        from app.engine import evaluate_all

        assert evaluate_all(snap([item(sched(every_km=7_500), archived=True)]), TODAY) == []

    def test_item_without_schedules_produces_nothing(self):
        from app.engine import evaluate_all

        assert evaluate_all(snap([item()]), TODAY) == []
