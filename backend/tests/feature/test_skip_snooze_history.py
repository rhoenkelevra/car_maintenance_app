"""Skip, snooze, the merged history, export and the development seed."""

import pytest

from .conftest import EVERY_7500_KM, sid, trigger


@pytest.fixture
def due_oil(api, car):
    """Oil every 7,500 km, done at 93,000 km, odometer now at 100,600 (orange)."""
    oil = api.item("Óleo do motor", EVERY_7500_KM, jp_term="エンジンオイル交換")
    api.maint("2026-11-02", 93_000, oil["id"])
    api.odo("2026-11-09", 100_600)
    assert api.notified() == {sid(oil): "due"}
    return oil


class TestSkip:
    def test_skip_clears_the_row_and_restarts_the_cycle(self, api, due_oil):
        response = api.action(due_oil, "skip", {"note": "troquei há pouco, sem recibo"})
        assert response.status_code == 201
        event = response.json()
        assert (event["type"], event["date"], event["km"]) == ("skip", "2026-11-09", 100_600)
        assert event["note"] == "troquei há pouco, sem recibo"

        assert api.notified() == {}
        assert trigger(api.status(sid(due_oil)), "km")["due_km"] == 108_100

    def test_skip_is_kept_in_the_history(self, client, api, due_oil):
        api.action(due_oil, "skip", {"note": "sem recibo"})
        entry = client.get("/api/history").json()[0]
        assert entry["kind"] == "skip"
        assert entry["item_names"] == ["Óleo do motor"]
        assert (entry["date"], entry["km"], entry["notes"]) == ("2026-11-09", 100_600, "sem recibo")

    def test_undoing_a_skip_brings_the_row_back(self, client, api, due_oil):
        event = api.action(due_oil, "skip").json()
        assert client.delete(f"/api/events/{event['id']}").status_code == 204
        assert api.notified() == {sid(due_oil): "due"}
        assert client.delete(f"/api/events/{event['id']}").status_code == 404

    def test_cannot_skip_without_history(self, api, car):
        oil = api.item("Óleo do motor", EVERY_7500_KM)
        response = api.action(oil, "skip")
        assert response.status_code == 409
        assert "Nada para pular" in response.json()["detail"]

    def test_fixed_date_can_only_be_skipped_inside_its_window(self, api, car, clock):
        shaken = api.item(
            "Vistoria (shaken)",
            {"type": "interval", "anchor": "fixed", "every_months": 24, "first_due_date": "2027-03-20"},
        )
        early = api.action(shaken, "skip")
        assert early.status_code == 409
        assert "período de aviso" in early.json()["detail"]

        clock.set("2027-03-01")
        assert api.action(shaken, "skip").status_code == 201
        assert trigger(api.status(sid(shaken)), "date")["due_date"] == "2029-03-20"

    def test_finished_one_time_event_cannot_be_skipped(self, api, car):
        plugs = api.item("Velas de ignição", {"type": "one_time", "at_km": 93_200})
        api.maint("2026-11-09", 93_100, plugs["id"])
        assert api.status(sid(plugs))["status"] == "done"
        assert api.action(plugs, "skip").status_code == 409

    def test_unknown_schedule_is_404(self, client, due_oil):
        url = f"/api/items/{due_oil['id']}/schedules/nope/skip"
        assert client.post(url, json={}).status_code == 404


class TestSnooze:
    def test_snooze_to_a_km_hides_the_row_until_then(self, api, due_oil):
        response = api.action(due_oil, "snooze", {"until_km": 105_000, "note": "óleo ainda bom"})
        assert response.status_code == 201
        assert response.json()["until_km"] == 105_000

        assert api.notified() == {}
        status = api.status(sid(due_oil))
        assert (status["status"], status["raw_status"], status["snoozed"]) == ("ok", "due", True)
        assert status["snooze_until_km"] == 105_000

        api.odo("2026-11-09", 104_300)
        assert api.notified() == {sid(due_oil): "upcoming"}
        api.odo("2026-11-09", 105_000)
        assert api.notified() == {sid(due_oil): "due"}

    def test_snooze_to_a_date(self, api, due_oil, clock):
        assert api.action(due_oil, "snooze", {"until_date": "2026-12-15"}).status_code == 201
        assert api.notified() == {}
        clock.set("2026-12-15")
        row = api.dashboard()["notifications"][0]
        assert (row["status"], row["driving"], row["snoozed"]) == ("due", "date", True)

    def test_registering_the_maintenance_ends_the_snooze(self, api, due_oil, clock):
        api.action(due_oil, "snooze", {"until_km": 105_000})
        clock.set("2026-11-20")
        api.maint("2026-11-20", 101_000, due_oil["id"])
        status = api.status(sid(due_oil))
        assert status["snoozed"] is False
        assert trigger(status, "km")["due_km"] == 108_500

    def test_snooze_is_kept_in_the_history_and_can_be_undone(self, client, api, due_oil):
        event = api.action(due_oil, "snooze", {"until_km": 105_000, "note": "óleo ainda bom"}).json()
        entry = client.get("/api/history").json()[0]
        assert (entry["kind"], entry["until_km"], entry["notes"]) == (
            "snooze",
            105_000,
            "óleo ainda bom",
        )
        assert client.delete(f"/api/events/{event['id']}").status_code == 204
        assert api.notified() == {sid(due_oil): "due"}

    def test_nothing_to_snooze_when_it_is_not_in_the_table(self, api, car):
        oil = api.item("Óleo do motor", {**EVERY_7500_KM, "baseline_km": 93_000})
        response = api.action(oil, "snooze", {"until_km": 99_000})
        assert response.status_code == 409
        assert "Nada para adiar" in response.json()["detail"]

    def test_cannot_snooze_without_history(self, api, car):
        oil = api.item("Óleo do motor", EVERY_7500_KM)
        assert api.action(oil, "snooze", {"until_km": 99_000}).status_code == 409

    @pytest.mark.parametrize(
        "body, message",
        [
            ({}, "até que km ou data"),
            ({"until_km": 100_600}, "maior que o km atual"),
            ({"until_km": 99_000}, "maior que o km atual"),
            ({"until_date": "2026-11-09"}, "depois de hoje"),
            ({"until_date": "2026-01-01"}, "depois de hoje"),
        ],
    )
    def test_validation(self, api, due_oil, body, message):
        response = api.action(due_oil, "snooze", body)
        assert response.status_code == 422
        assert message in response.json()["detail"]
        assert api.status(sid(due_oil))["snoozed"] is False


class TestHistory:
    def test_records_skips_and_snoozes_newest_first(self, client, api, car, clock):
        oil = api.item("Óleo do motor", EVERY_7500_KM)
        tyres = api.item("Rodízio de pneus", {"type": "interval", "every_km": 5_000})
        api.maint("2026-11-02", 93_000, oil["id"], tyres["id"], cost_total=12_800)
        clock.set("2027-02-01")
        api.odo("2027-02-01", 98_200)
        api.action(tyres, "snooze", {"until_km": 99_000})
        clock.set("2027-03-01")
        api.odo("2027-03-01", 100_700)
        api.action(oil, "skip")

        history = client.get("/api/history").json()
        assert [(h["kind"], h["date"], h["item_names"]) for h in history] == [
            ("skip", "2027-03-01", ["Óleo do motor"]),
            ("snooze", "2027-02-01", ["Rodízio de pneus"]),
            ("maintenance", "2026-11-02", ["Óleo do motor", "Rodízio de pneus"]),
        ]
        assert history[2]["cost_total"] == 12_800
        assert history[1]["until_km"] == 99_000

    def test_empty_history(self, client, car):
        assert client.get("/api/history").json() == []


class TestExport:
    def test_export_contains_everything(self, client, api, due_oil):
        api.fuel("2026-11-09", 100_650, litres=30.5, price_total=5_246)
        api.action(due_oil, "snooze", {"until_km": 105_000})

        export = client.get("/api/export").json()
        assert export["exported_at"]
        assert export["car"] == client.get("/api/car").json()
        assert export["items"] == client.get("/api/items").json()
        assert export["fuel"] == client.get("/api/fuel").json()
        assert export["odometer"] == client.get("/api/odometer").json()
        assert export["maintenance"] == client.get("/api/maintenance").json()
        assert [e["type"] for e in export["events"]] == ["snooze"]
        assert export["fuel"][0]["litres"] == 30.5

    def test_export_includes_archived_items(self, client, api, due_oil):
        client.delete(f"/api/items/{due_oil['id']}")
        export = client.get("/api/export").json()
        assert [(i["name"], i["archived"]) for i in export["items"]] == [("Óleo do motor", True)]


class TestDevSeed:
    def test_disabled_unless_enabled_by_the_environment(self, client, monkeypatch):
        monkeypatch.delenv("ENABLE_DEV_SEED", raising=False)
        assert client.post("/api/dev/seed").status_code == 404
        assert client.get("/api/car").json() is None

    def test_loads_the_prius_and_its_items(self, client, api, monkeypatch):
        monkeypatch.setenv("ENABLE_DEV_SEED", "1")
        response = client.post("/api/dev/seed")
        assert response.json() == {"items": 18, "fuel": 0, "maintenance": 0}

        car = client.get("/api/car").json()
        assert (car["maker"], car["model"], car["model_code"], car["year"]) == (
            "Toyota",
            "Prius",
            "ZVW30",
            2014,
        )
        assert (car["start_km"], car["shaken_expiry"]) == (93_000, "2027-03-20")

        items = {i["name"]: i for i in client.get("/api/items").json()}
        assert len(items) == 18
        assert items["Óleo do motor"]["jp_term"] == "エンジンオイル交換"
        oil = items["Óleo do motor"]["schedules"][0]
        assert (oil["every_km"], oil["every_months"]) == (7_500, 6)  # severe use
        assert items["Líquido do inversor"]["schedules"] == []

        by_name = {s["item_name"]: s for s in api.dashboard()["statuses"]}
        assert by_name["Óleo do motor"]["status"] == "no_history"
        assert by_name["Fluido do transeixo (e-CVT)"]["status"] == "upcoming"  # 93k of 100k
        assert by_name["Velas de ignição"]["status"] == "ok"
        assert trigger(by_name["Vistoria (shaken)"], "date")["due_date"] == "2027-03-20"
        assert trigger(by_name["Inspeção de 12 meses"], "date")["due_date"] == "2028-03-20"
        assert trigger(by_name["Imposto do automóvel"], "date")["due_date"] == "2027-05-31"

    def test_seed_replaces_what_was_there(self, client, api, car, monkeypatch):
        monkeypatch.setenv("ENABLE_DEV_SEED", "1")
        api.item("Item antigo")
        api.fuel("2026-11-05", 93_400)
        client.post("/api/dev/seed")
        assert "Item antigo" not in [i["name"] for i in client.get("/api/items").json()]
        assert client.get("/api/fuel").json() == []

    def test_demo_seed_shows_every_status(self, client, api, monkeypatch):
        monkeypatch.setenv("ENABLE_DEV_SEED", "1")
        response = client.post("/api/dev/seed?demo=true")
        assert response.json() == {"items": 18, "fuel": 8, "maintenance": 3}

        d = api.dashboard()
        by_name = {s["item_name"]: s["status"] for s in d["statuses"]}
        assert by_name["Calibragem dos pneus"] == "overdue"
        assert by_name["Óleo do motor"] == "due"
        assert by_name["Aditivo de combustível"] == "upcoming"
        assert by_name["Filtro de óleo"] == "ok"
        assert by_name["Fluido de freio"] == "no_history"
        assert d["current_km"] == 95_950
        assert [n["status"] for n in d["notifications"]][:3] == ["overdue", "due", "upcoming"]
