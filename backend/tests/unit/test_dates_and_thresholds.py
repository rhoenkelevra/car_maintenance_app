from datetime import date

import pytest

from app.engine import (
    add_months,
    day_lead,
    day_margin,
    fillup_lead,
    fillup_margin,
    km_lead,
    km_margin,
    level,
    pinned_date,
    ten_percent,
)

from .helpers import sched


class TestAddMonths:
    @pytest.mark.parametrize(
        "start, months, expected",
        [
            (date(2026, 1, 10), 6, date(2026, 7, 10)),
            (date(2026, 8, 31), 6, date(2027, 2, 28)),  # month end clamps
            (date(2027, 8, 31), 6, date(2028, 2, 29)),  # leap year
            (date(2026, 1, 31), 1, date(2026, 2, 28)),
            (date(2026, 12, 15), 1, date(2027, 1, 15)),  # year rollover
            (date(2027, 3, 20), 24, date(2029, 3, 20)),
            (date(2028, 2, 29), 12, date(2029, 2, 28)),
            (date(2026, 5, 31), 0, date(2026, 5, 31)),
        ],
    )
    def test_adds_calendar_months(self, start, months, expected):
        assert add_months(start, months) == expected


class TestPinnedDate:
    def test_keeps_a_valid_day(self):
        assert pinned_date(2027, 5, 31) == date(2027, 5, 31)

    def test_clamps_to_month_end(self):
        assert pinned_date(2027, 2, 31) == date(2027, 2, 28)
        assert pinned_date(2028, 2, 31) == date(2028, 2, 29)
        assert pinned_date(2027, 11, 31) == date(2027, 11, 30)


class TestTenPercent:
    @pytest.mark.parametrize(
        "value, expected", [(7_500, 750), (100_000, 10_000), (3, 1), (1, 1), (180, 18), (25, 2)]
    )
    def test_is_ten_percent_with_a_minimum_of_one(self, value, expected):
        assert ten_percent(value) == expected


class TestLevel:
    """Oil at 7,500 km: yellow at 6,750, orange at 7,500, red at 8,250."""

    @pytest.mark.parametrize(
        "current, expected",
        [
            (0, "ok"),
            (6_749, "ok"),
            (6_750, "upcoming"),
            (7_499, "upcoming"),
            (7_500, "due"),
            (8_249, "due"),
            (8_250, "overdue"),
            (20_000, "overdue"),
        ],
    )
    def test_boundaries(self, current, expected):
        assert level(current, due=7_500, lead=750, margin=750) == expected

    def test_zero_lead_never_shows_yellow(self):
        assert level(7_499, due=7_500, lead=0, margin=750) == "ok"
        assert level(7_500, due=7_500, lead=0, margin=750) == "due"

    def test_zero_margin_goes_straight_to_red(self):
        assert level(7_499, due=7_500, lead=750, margin=0) == "upcoming"
        assert level(7_500, due=7_500, lead=750, margin=0) == "overdue"


class TestDefaultThresholds:
    def test_km_is_ten_percent_of_the_interval(self):
        s = sched(every_km=7_500)
        assert (km_lead(s), km_margin(s)) == (750, 750)

    def test_km_overrides_win(self):
        s = sched(every_km=7_500, lead_km=2_000, overdue_km=100)
        assert (km_lead(s), km_margin(s)) == (2_000, 100)

    def test_km_override_of_zero_is_respected(self):
        s = sched(every_km=7_500, lead_km=0, overdue_km=0)
        assert (km_lead(s), km_margin(s)) == (0, 0)

    @pytest.mark.parametrize("months, days", [(1, 3), (6, 18), (12, 36), (24, 72), (48, 144)])
    def test_days_count_a_month_as_thirty_days(self, months, days):
        s = sched(every_months=months)
        assert (day_lead(s), day_margin(s)) == (days, days)

    def test_day_overrides_win(self):
        s = sched(every_months=6, lead_days=60, overdue_days=5)
        assert (day_lead(s), day_margin(s)) == (60, 5)

    def test_yearly_uses_the_gap_between_pinned_months(self):
        assert day_lead(sched(type="yearly", months=[5])) == 36
        assert day_lead(sched(type="yearly", months=[5, 11])) == 18

    def test_one_time_defaults_to_500_km_and_30_days(self):
        s = sched(type="one_time", at_km=100_000, on_date=date(2027, 1, 1))
        assert (km_lead(s), km_margin(s), day_lead(s), day_margin(s)) == (500, 500, 30, 30)

    def test_interval_without_a_month_trigger_falls_back_to_30_days(self):
        # Used when a km-only schedule is snoozed to a date.
        assert day_lead(sched(every_km=7_500)) == 30

    @pytest.mark.parametrize("every, lead, margin", [(1, 0, 1), (2, 1, 1), (3, 1, 1), (20, 2, 2)])
    def test_fillups(self, every, lead, margin):
        assert (fillup_lead(every), fillup_margin(every)) == (lead, margin)


class TestFmtKm:
    @pytest.mark.parametrize(
        "km, text", [(0, "0 km"), (950, "950 km"), (93_400, "93.400 km"), (1_250_000, "1.250.000 km")]
    )
    def test_uses_pt_br_thousands(self, km, text):
        from app.engine import fmt_km

        assert fmt_km(km) == text
