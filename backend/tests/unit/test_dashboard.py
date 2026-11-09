"""Current km, pace, projection, stale odometer and the notification table."""

from datetime import date, timedelta

import pytest

from app.engine import Point, compute_pace

from .helpers import (
    START_DATE,
    START_KM,
    TODAY,
    car,
    dashboard,
    days_ago,
    fuel,
    item,
    maint,
    odo,
    sched,
    snap,
    status_of,
    trigger,
)


class TestCurrentKm:
    def test_a_new_car_is_at_its_starting_km(self):
        d = dashboard(snap())
        assert (d.current_km, d.last_reading_date) == (START_KM, START_DATE)

    def test_takes_the_highest_km_from_every_kind_of_log(self):
        snapshot = snap(
            [item(sched(every_km=7_500))],
            fuel=[fuel(days_ago(20), 94_000)],
            odometer=[odo(days_ago(10), 94_500)],
            maintenance=[maint(days_ago(5), 94_800)],
        )
        d = dashboard(snapshot)
        assert (d.current_km, d.last_reading_date) == (94_800, days_ago(5))

    def test_today_is_echoed(self):
        assert dashboard(snap()).today == TODAY


class TestPace:
    def test_uses_the_last_90_days_when_they_have_enough_data(self):
        points = [
            Point(START_DATE, START_KM),
            Point(days_ago(60), 95_000),
            Point(days_ago(10), 95_500),
        ]
        assert compute_pace(points, TODAY) == pytest.approx(10.0)

    def test_falls_back_to_all_readings(self):
        # Only one reading in the window: use the whole history instead.
        points = [Point(START_DATE, START_KM), Point(days_ago(10), 95_500)]
        span = (days_ago(10) - START_DATE).days
        assert compute_pace(points, TODAY) == pytest.approx(2_500 / span)

    def test_needs_readings_at_least_a_week_apart(self):
        assert compute_pace([Point(days_ago(6), 93_000), Point(TODAY, 93_100)], TODAY) is None
        assert compute_pace([Point(days_ago(7), 93_000), Point(TODAY, 93_070)], TODAY) == (
            pytest.approx(10.0)
        )

    def test_none_with_a_single_reading(self):
        assert compute_pace([Point(TODAY, 93_000)], TODAY) is None

    def test_zero_when_the_car_did_not_move(self):
        assert compute_pace([Point(days_ago(30), 93_000), Point(TODAY, 93_000)], TODAY) == 0

    def test_dashboard_reports_the_pace(self):
        snapshot = snap(odometer=[odo(days_ago(60), 95_000), odo(days_ago(10), 95_500)])
        assert dashboard(snapshot).pace_km_per_day == 10.0


class TestProjection:
    """Pace is 10 km a day; the last reading was 10 days ago at 95,500 km."""

    READINGS = [(60, 95_000), (10, 95_500)]

    def snapshot(self, schedule):
        return snap([item(schedule)], odometer=[odo(days_ago(d), km) for d, km in self.READINGS])

    def test_projects_the_due_date_from_the_pace(self):
        # Due at 96,500: 1,000 km to go is 100 days after the last reading.
        s = sched(every_km=10_000, baseline_km=86_500)
        status = status_of(self.snapshot(s))
        assert trigger(status, "km").projected_date == days_ago(10) + timedelta(days=100)
        assert status.estimated_due_date == TODAY + timedelta(days=90)

    def test_projection_is_never_in_the_past(self):
        # 50 km to go was 5 days of driving, 10 days ago: probably due already.
        s = sched(every_km=10_000, baseline_km=85_550)
        assert trigger(status_of(self.snapshot(s)), "km").projected_date == TODAY

    def test_no_projection_once_due(self):
        s = sched(every_km=10_000, baseline_km=85_000)
        status = status_of(self.snapshot(s))
        assert status.status == "due"
        assert trigger(status, "km").projected_date is None

    def test_no_projection_without_a_pace(self):
        s = sched(every_km=10_000, baseline_km=86_500)
        new_car = snap([item(s)], car_=car(start_date=days_ago(2)))
        assert trigger(status_of(new_car), "km").projected_date is None

    def test_estimated_due_date_is_the_earliest_of_date_and_projection(self):
        s = sched(
            every_km=10_000, every_months=6, baseline_km=86_500, baseline_date=days_ago(160)
        )
        status = status_of(self.snapshot(s))
        date_due = trigger(status, "date").due_date
        assert date_due < trigger(status, "km").projected_date
        assert status.estimated_due_date == date_due


class TestStaleOdometer:
    def test_not_stale_at_exactly_30_days(self):
        d = dashboard(snap(odometer=[odo(days_ago(30), 96_000)]))
        assert d.stale is False

    def test_stale_after_30_days(self):
        d = dashboard(snap(odometer=[odo(days_ago(31), 96_000)]))
        assert d.stale is True

    def test_estimated_km_extends_the_last_reading_by_the_pace(self):
        d = dashboard(snap(odometer=[odo(days_ago(31), 96_000)]))
        pace = 3_000 / (days_ago(31) - START_DATE).days
        assert d.estimated_km == 96_000 + round(pace * 31)

    def test_no_estimate_without_a_pace(self):
        d = dashboard(snap(car_=car(start_date=days_ago(2))))
        assert d.estimated_km is None
        assert d.pace_km_per_day is None

    def test_statuses_use_the_logged_km_not_the_estimate(self):
        # Estimated km is past due, but the last logged km is not.
        s = sched(every_km=10_000, baseline_km=86_100)  # due at 96,100
        d = dashboard(snap([item(s)], odometer=[odo(days_ago(31), 96_000)]))
        assert d.estimated_km > 96_100
        assert d.notifications[0].status == "upcoming"


class TestNotifications:
    def snapshot(self):
        ok = item(sched(id="ok", every_km=7_500, baseline_km=93_000), id="a", name="Zeta ok")
        grey = item(sched(id="grey", every_km=7_500), id="b", name="Alfa sem histórico")
        yellow = item(sched(id="yellow", every_km=7_500, baseline_km=86_000), id="c", name="Bravo")
        orange = item(sched(id="orange", every_km=7_500, baseline_km=85_400), id="d", name="Charlie")
        red = item(sched(id="red", every_km=7_500, baseline_km=80_000), id="e", name="Delta")
        red2 = item(sched(id="red2", every_km=7_500, baseline_km=80_000), id="f", name="alfa atrasado")
        done = item(sched(id="done", type="one_time", at_km=93_100), id="g", name="Feito")
        return snap([ok, grey, yellow, orange, red, red2, done], maintenance=[maint(TODAY, 93_000, "g")])

    def test_sorted_red_orange_yellow_grey_then_by_name(self):
        d = dashboard(self.snapshot())
        assert [(n.schedule_id, n.status) for n in d.notifications] == [
            ("red2", "overdue"),
            ("red", "overdue"),
            ("orange", "due"),
            ("yellow", "upcoming"),
            ("grey", "no_history"),
        ]

    def test_ok_and_done_are_left_out_of_the_table(self):
        d = dashboard(self.snapshot())
        assert {n.schedule_id for n in d.notifications}.isdisjoint({"ok", "done"})

    def test_statuses_list_everything(self):
        d = dashboard(self.snapshot())
        by_id = {s.schedule_id: s.status for s in d.statuses}
        assert by_id["ok"] == "ok"
        assert by_id["done"] == "done"
        assert len(by_id) == 7

    def test_rows_carry_the_item_name_and_japanese_term(self):
        row = dashboard(self.snapshot()).notifications[0]
        assert row.item_name == "alfa atrasado"
        assert row.jp_term == "エンジンオイル交換"
        assert row.item_id == "f"

    def test_empty_car_has_no_notifications(self):
        d = dashboard(snap())
        assert d.notifications == [] and d.statuses == []


class TestDateHandling:
    def test_status_changes_at_midnight_of_the_given_day(self):
        s = sched(every_months=1, baseline_date=date(2026, 10, 9))  # due 2026-11-09
        snapshot = snap([item(s)])
        assert status_of(snapshot, date(2026, 11, 8)).status == "upcoming"
        assert status_of(snapshot, date(2026, 11, 9)).status == "due"
