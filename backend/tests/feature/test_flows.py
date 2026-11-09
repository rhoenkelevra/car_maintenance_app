"""Whole flows through the API, the way the app is really used."""

from .conftest import EVERY_6_MONTHS, EVERY_7500_KM, sid, trigger


class TestOilByKm:
    def test_grey_then_yellow_orange_red_then_cleared(self, api, car, clock):
        oil = api.item("Óleo do motor", EVERY_7500_KM, jp_term="エンジンオイル交換")
        s = sid(oil)

        # A used car: nobody knows when the oil was last changed.
        assert api.notified() == {s: "no_history"}

        # "Começar a contar de hoje": counts from 93,000 km, due at 100,500.
        assert api.action(oil, "baseline", {"today": True}).status_code == 200
        assert api.notified() == {}
        assert trigger(api.status(s), "km")["due_km"] == 100_500

        clock.set("2026-12-01")
        api.fuel("2026-12-01", 99_700)
        assert api.notified() == {}  # 800 km to go: not yet in the table

        api.fuel("2026-12-01", 99_800)
        row = api.dashboard()["notifications"][0]
        assert (row["status"], row["driving"]) == ("upcoming", "km")
        assert (row["item_name"], row["jp_term"]) == ("Óleo do motor", "エンジンオイル交換")
        assert trigger(row, "km")["remaining"] == 700

        clock.set("2026-12-20")
        api.fuel("2026-12-20", 100_500)
        assert api.notified() == {s: "due"}

        clock.set("2027-01-10")
        api.fuel("2027-01-10", 101_300)
        assert api.notified() == {s: "overdue"}
        assert trigger(api.status(s), "km")["remaining"] == -800

        # Registering the maintenance is the only thing that clears the row.
        api.maint("2027-01-10", 101_300, oil["id"], cost_total=6_800)
        assert api.notified() == {}
        status = api.status(s)
        assert status["status"] == "ok"
        assert trigger(status, "km")["due_km"] == 108_800  # counted from when it was done
        assert (status["last_done_date"], status["last_done_km"]) == ("2027-01-10", 101_300)


class TestByTime:
    def test_six_month_item_comes_due_without_any_driving(self, api, car, clock):
        coating = api.item("Reaplicar coating", EVERY_6_MONTHS)
        s = sid(coating)
        api.maint("2026-11-09", 93_000, coating["id"])
        assert api.notified() == {}

        clock.set("2027-04-20")
        assert api.notified() == {}
        clock.set("2027-04-21")  # 18 days before 2027-05-09
        assert api.notified() == {s: "upcoming"}
        clock.set("2027-05-09")
        assert api.notified() == {s: "due"}
        clock.set("2027-05-27")  # 18 days after
        assert api.notified() == {s: "overdue"}

        api.maint("2027-05-27", 93_000, coating["id"])
        assert api.notified() == {}
        assert trigger(api.status(s), "date")["due_date"] == "2027-11-27"

    def test_oil_by_km_or_months_fires_on_time_for_short_trips(self, api, car, clock):
        oil = api.item("Óleo do motor", {"type": "interval", "every_km": 7_500, "every_months": 6})
        api.maint("2026-11-09", 93_000, oil["id"])
        clock.set("2027-05-09")
        api.fuel("2027-05-09", 94_200)  # only 1,200 km in six months
        row = api.dashboard()["notifications"][0]
        assert (row["status"], row["driving"]) == ("due", "date")
        assert trigger(row, "km")["status"] == "ok"


class TestAdditiveByFillups:
    def test_every_three_fillups(self, api, car, clock):
        additive = api.item(
            "Aditivo de combustível",
            {"type": "interval", "every_fillups": 3, "every_km": 5_000},
            jp_term="燃料添加剤",
        )
        s = sid(additive)

        # First tank: fuel and additive on the same visit. That tank does not count.
        api.fuel("2026-11-09", 93_400)
        api.maint("2026-11-09", 93_400, additive["id"])
        assert trigger(api.status(s), "fillups")["remaining"] == 3

        clock.set("2026-11-20")
        api.fuel("2026-11-20", 93_800, full_tank=False)  # a partial fill counts too
        assert api.notified() == {}

        clock.set("2026-12-01")
        api.fuel("2026-12-01", 94_200)
        assert api.notified() == {s: "upcoming"}

        clock.set("2026-12-12")
        api.fuel("2026-12-12", 94_600)
        row = api.dashboard()["notifications"][0]
        assert (row["status"], row["driving"]) == ("due", "fillups")

        api.maint("2026-12-12", 94_600, additive["id"])
        assert api.notified() == {}
        assert trigger(api.status(s), "fillups")["remaining"] == 3


class TestOneVisitManyItems:
    def test_one_record_clears_several_rows(self, client, api, car, clock):
        oil = api.item("Óleo do motor", EVERY_7500_KM)
        filt = api.item("Filtro de óleo", EVERY_7500_KM)
        brake = api.item("Fluido de freio", {"type": "interval", "every_months": 24})
        tyres = api.item("Rodízio de pneus", {"type": "interval", "every_km": 5_000})
        api.maint("2026-11-09", 93_000, oil["id"], filt["id"], brake["id"], tyres["id"])

        clock.set("2027-03-01")
        api.odo("2027-03-01", 100_600)
        assert api.notified() == {sid(oil): "due", sid(filt): "due", sid(tyres): "overdue"}

        api.maint(
            "2027-03-01", 100_600, oil["id"], filt["id"], cost_total=9_900, shop="Concessionária"
        )
        assert api.notified() == {sid(tyres): "overdue"}  # not part of that visit

        entry = client.get("/api/history").json()[0]
        assert entry["item_names"] == ["Óleo do motor", "Filtro de óleo"]
        assert (entry["cost_total"], entry["shop"]) == (9_900, "Concessionária")


class TestCorrections:
    def test_statuses_follow_edits_and_deletes(self, client, api, car):
        oil = api.item("Óleo do motor", EVERY_7500_KM)
        s = sid(oil)
        api.maint("2026-11-02", 93_000, oil["id"])
        reading = api.odo("2026-11-05", 100_600)
        assert api.notified() == {s: "due"}

        done = api.maint("2026-11-06", 100_600, oil["id"])
        assert api.notified() == {}

        # Registered by mistake: deleting it brings the notification back.
        client.delete(f"/api/maintenance/{done['id']}")
        assert api.notified() == {s: "due"}

        # Register it again, then correct its km.
        done = api.maint("2026-11-06", 100_600, oil["id"])
        body = {"date": "2026-11-06", "km": 100_700, "item_ids": [oil["id"]]}
        assert client.put(f"/api/maintenance/{done['id']}", json=body).status_code == 200
        assert trigger(api.status(s), "km")["due_km"] == 108_200

        client.delete(f"/api/odometer/{reading['id']}")
        assert api.dashboard()["current_km"] == 100_700

    def test_fixing_a_typo_in_a_fuel_log_changes_the_status(self, client, api, car):
        oil = api.item("Óleo do motor", {**EVERY_7500_KM, "baseline_km": 93_000})
        log = api.fuel("2026-11-09", 109_000)  # meant 99,000
        assert api.notified() == {sid(oil): "overdue"}
        body = {"date": "2026-11-09", "km": 99_000}
        assert client.put(f"/api/fuel/{log['id']}", json=body).status_code == 200
        assert api.notified() == {}

    def test_removing_the_item_from_a_record_restores_its_row(self, client, api, car):
        oil = api.item("Óleo do motor", {**EVERY_7500_KM, "baseline_km": 85_000})
        filt = api.item("Filtro de óleo", {**EVERY_7500_KM, "baseline_km": 85_000})
        record = api.maint("2026-11-09", 93_000, oil["id"], filt["id"])
        assert api.notified() == {}
        body = {"date": "2026-11-09", "km": 93_000, "item_ids": [oil["id"]]}
        client.put(f"/api/maintenance/{record['id']}", json=body)
        assert api.notified() == {sid(filt): "due"}


class TestBaseline:
    def test_inform_when_it_was_last_done(self, api, car):
        oil = api.item("Óleo do motor", {"type": "interval", "every_km": 7_500, "every_months": 6})
        s = sid(oil)
        assert api.notified() == {s: "no_history"}

        response = api.action(oil, "baseline", {"km": 90_000, "date": "2026-08-01"})
        assert response.status_code == 200
        stored = response.json()["schedules"][0]
        assert (stored["baseline_km"], stored["baseline_date"]) == (90_000, "2026-08-01")

        status = api.status(s)
        assert status["status"] == "ok"
        assert trigger(status, "km")["due_km"] == 97_500
        assert trigger(status, "date")["due_date"] == "2027-02-01"

    def test_start_counting_from_today(self, api, car):
        api.fuel("2026-11-08", 93_650)
        oil = api.item("Óleo do motor", {"type": "interval", "every_km": 7_500, "every_months": 6})
        stored = api.action(oil, "baseline", {"today": True}).json()["schedules"][0]
        assert (stored["baseline_km"], stored["baseline_date"]) == (93_650, "2026-11-09")

    def test_km_only_schedule_needs_only_the_km(self, api, car):
        cvt = api.item("Fluido do transeixo", {"type": "interval", "every_km": 100_000})
        assert api.action(cvt, "baseline", {"km": 0}).status_code == 200
        assert api.notified() == {sid(cvt): "upcoming"}  # 93,000 of 100,000 km

    def test_a_later_record_overrides_the_manual_baseline(self, api, car):
        oil = api.item("Óleo do motor", EVERY_7500_KM)
        api.action(oil, "baseline", {"km": 90_000})
        api.maint("2026-11-09", 93_200, oil["id"])
        assert trigger(api.status(sid(oil)), "km")["due_km"] == 100_700

    def test_validation(self, client, api, car):
        oil = api.item("Óleo do motor", {"type": "interval", "every_km": 7_500, "every_months": 6})

        assert api.action(oil, "baseline", {}).status_code == 422
        future = api.action(oil, "baseline", {"km": 90_000, "date": "2026-11-10"})
        assert future.status_code == 422 and "futuro" in future.json()["detail"]
        ahead = api.action(oil, "baseline", {"km": 93_001, "date": "2026-11-01"})
        assert ahead.status_code == 422 and "km atual" in ahead.json()["detail"]
        partial = api.action(oil, "baseline", {"km": 90_000})
        assert partial.status_code == 422 and "data da última vez" in partial.json()["detail"]
        assert api.notified() == {sid(oil): "no_history"}

    def test_only_interval_schedules_have_a_baseline(self, api, car):
        tax = api.item("Imposto", {"type": "yearly", "months": [5], "day": 31})
        assert api.action(tax, "baseline", {"today": True}).status_code == 400

    def test_unknown_schedule_is_404(self, client, api, car):
        oil = api.item("Óleo do motor", EVERY_7500_KM)
        url = f"/api/items/{oil['id']}/schedules/nope/baseline"
        assert client.post(url, json={"today": True}).status_code == 404
        url = f"/api/items/nope/schedules/{sid(oil)}/baseline"
        assert client.post(url, json={"today": True}).status_code == 404


class TestOneTimeEvent:
    def test_oil_every_7500_km_and_once_at_100k(self, client, api, car):
        oil = api.item(
            "Óleo do motor", EVERY_7500_KM, {"type": "one_time", "at_km": 100_000}
        )
        every, once = sid(oil, 0), sid(oil, 1)

        # A normal oil change at 94,000 km must not finish the 100k event.
        api.maint("2026-11-03", 94_000, oil["id"])
        assert api.status(once)["status"] == "ok"
        assert trigger(api.status(every), "km")["due_km"] == 101_500

        api.odo("2026-11-08", 99_600)
        assert api.notified() == {once: "upcoming"}

        api.maint("2026-11-09", 99_600, oil["id"])
        assert api.notified() == {}
        assert api.status(once)["status"] == "done"
        assert trigger(api.status(every), "km")["due_km"] == 107_100
        assert len(client.get("/api/history").json()) == 2

    def test_never_done_goes_red(self, api, car):
        plugs = api.item("Velas de ignição", {"type": "one_time", "at_km": 100_000})
        api.odo("2026-11-09", 100_500)
        assert api.notified() == {sid(plugs): "overdue"}


class TestFixedAndPinnedDates:
    def test_shaken_keeps_its_fixed_dates(self, api, car, clock):
        shaken = api.item(
            "Vistoria (shaken)",
            {"type": "interval", "anchor": "fixed", "every_months": 24, "first_due_date": "2027-03-20"},
            jp_term="車検",
        )
        s = sid(shaken)
        assert api.notified() == {}  # no baseline needed

        clock.set("2027-01-07")
        assert api.notified() == {s: "upcoming"}

        clock.set("2027-02-10")
        api.maint("2027-02-10", 94_000, shaken["id"], cost_total=98_000)
        assert api.notified() == {}
        assert trigger(api.status(s), "date")["due_date"] == "2029-03-20"

    def test_yearly_tax_every_may(self, api, car, clock):
        tax = api.item("Imposto do automóvel", {"type": "yearly", "months": [5], "day": 31})
        s = sid(tax)
        assert trigger(api.status(s), "date")["due_date"] == "2027-05-31"

        clock.set("2027-04-25")
        assert api.notified() == {s: "upcoming"}
        clock.set("2027-06-02")
        assert api.notified() == {s: "due"}

        api.maint("2027-06-02", 93_000, tax["id"], cost_total=36_000)
        assert api.notified() == {}
        assert trigger(api.status(s), "date")["due_date"] == "2028-05-31"
