"""The odometer never goes backwards, but backdated entries that fit are fine."""

from datetime import date

from app.engine import Point, check_km_order

START_KM = 93_000
LOGGED = [
    Point(date(2026, 3, 1), 94_000),
    Point(date(2026, 4, 1), 95_000),
    Point(date(2026, 5, 1), 96_000),
]


def check(d: date, km: int, others=LOGGED) -> str | None:
    return check_km_order(d, km, others, START_KM)


class TestKmOrder:
    def test_first_entry_at_the_starting_km_is_fine(self):
        assert check(date(2026, 1, 5), 93_000, others=[]) is None

    def test_below_the_starting_km_is_rejected(self):
        assert "km inicial do carro (93.000 km)" in check(date(2026, 1, 5), 92_999, others=[])

    def test_new_entry_after_everything(self):
        assert check(date(2026, 6, 1), 96_500) is None

    def test_same_km_as_the_previous_entry_is_allowed(self):
        assert check(date(2026, 6, 1), 96_000) is None

    def test_lower_than_an_earlier_entry_is_rejected(self):
        message = check(date(2026, 6, 1), 95_999)
        assert "menor" in message and "96.000 km" in message

    def test_typo_far_above_is_fine_when_nothing_comes_after(self):
        # 152,000 instead of 125,000 cannot be caught here; it is fixed by editing.
        assert check(date(2026, 6, 1), 152_000) is None

    def test_backdated_entry_that_fits_between_neighbours(self):
        assert check(date(2026, 3, 15), 94_500) is None
        assert check(date(2026, 3, 15), 94_000) is None
        assert check(date(2026, 3, 15), 95_000) is None

    def test_backdated_entry_higher_than_a_later_one_is_rejected(self):
        message = check(date(2026, 3, 15), 95_001)
        assert "maior" in message and "95.000 km" in message

    def test_backdated_entry_lower_than_an_earlier_one_is_rejected(self):
        message = check(date(2026, 3, 15), 93_999)
        assert "menor" in message and "94.000 km" in message

    def test_entry_before_everything_must_not_exceed_the_first_one(self):
        assert check(date(2026, 2, 1), 93_500) is None
        assert check(date(2026, 2, 1), 94_001) is not None

    def test_same_date_entries_do_not_constrain_each_other(self):
        # Fuel and maintenance on the same day can carry any km between neighbours.
        assert check(date(2026, 4, 1), 94_200) is None
        assert check(date(2026, 4, 1), 95_900) is None
        assert check(date(2026, 4, 1), 96_001) is not None
        assert check(date(2026, 4, 1), 93_999) is not None
