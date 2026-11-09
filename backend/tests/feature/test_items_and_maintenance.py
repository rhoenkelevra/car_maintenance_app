"""CRUD and validation for items, their schedules and maintenance records."""

import pytest

from .conftest import EVERY_6_MONTHS, EVERY_7500_KM, sid


class TestItems:
    def test_create_assigns_ids_and_a_creation_date(self, client, api, car):
        item = api.item(
            "Óleo do motor",
            {"type": "interval", "every_km": 7_500, "every_months": 6},
            jp_term="エンジンオイル交換",
            notes="0W-20",
        )
        assert item["id"]
        assert item["jp_term"] == "エンジンオイル交換"
        assert item["archived"] is False
        schedule = item["schedules"][0]
        assert schedule["id"]
        assert schedule["created_on"] == "2026-11-09"
        assert (schedule["anchor"], schedule["active"]) == ("actual", True)
        assert client.get(f"/api/items/{item['id']}").json() == item

    def test_item_without_schedules_is_valid(self, api, car):
        item = api.item("Bateria trocada na estrada")
        assert item["schedules"] == []
        assert api.dashboard()["statuses"] == []

    def test_list_is_sorted_by_name(self, client, api, car):
        for name in ["Velas", "aditivo", "Óleo do motor", "Filtro de ar"]:
            api.item(name)
        names = [i["name"] for i in client.get("/api/items").json()]
        assert names == sorted(names, key=str.lower)

    def test_every_schedule_type_round_trips(self, client, api, car):
        item = api.item(
            "Vários",
            {"type": "interval", "every_fillups": 3, "every_km": 5_000},
            {"type": "interval", "anchor": "fixed", "every_months": 24, "first_due_date": "2027-03-20"},
            {"type": "yearly", "months": [11, 5], "day": 31},
            {"type": "one_time", "at_km": 100_000, "on_date": "2027-06-01"},
            {"type": "interval", "every_km": 7_500, "lead_km": 1_000, "overdue_km": 0, "active": False},
        )
        stored = client.get(f"/api/items/{item['id']}").json()["schedules"]
        assert stored[0]["every_fillups"] == 3
        assert (stored[1]["anchor"], stored[1]["first_due_date"]) == ("fixed", "2027-03-20")
        assert (stored[2]["months"], stored[2]["day"]) == ([5, 11], 31)
        assert (stored[3]["at_km"], stored[3]["on_date"]) == (100_000, "2027-06-01")
        assert (stored[4]["lead_km"], stored[4]["overdue_km"], stored[4]["active"]) == (1_000, 0, False)
        assert len({s["id"] for s in stored}) == 5

    @pytest.mark.parametrize(
        "schedule, message",
        [
            ({"type": "interval"}, "ao menos um intervalo"),
            ({"type": "interval", "anchor": "fixed", "every_months": 24}, "primeiro vencimento"),
            ({"type": "yearly"}, "ao menos um mês"),
            ({"type": "yearly", "months": [13]}, "Mês inválido"),
            ({"type": "one_time"}, "evento único"),
            ({"type": "interval", "every_months": 6, "baseline_km": 90_000}, "data da última vez"),
        ],
    )
    def test_invalid_schedules_are_rejected_with_a_message(self, client, car, schedule, message):
        response = client.post("/api/items", json={"name": "X", "schedules": [schedule]})
        assert response.status_code == 422
        assert message in response.json()["detail"]
        assert client.get("/api/items").json() == []

    def test_name_is_required(self, client, car):
        assert client.post("/api/items", json={"name": ""}).status_code == 422
        assert client.post("/api/items", json={}).status_code == 422

    def test_update_keeps_schedule_ids_and_creation_dates(self, client, api, car, clock):
        item = api.item("Óleo do motor", EVERY_7500_KM)
        original = item["schedules"][0]
        clock.set("2026-12-01")
        body = {
            "name": "Óleo do motor (sintético)",
            "jp_term": "エンジンオイル交換",
            "notes": "",
            "schedules": [{**original, "every_km": 5_000}, EVERY_6_MONTHS],
        }
        response = client.put(f"/api/items/{item['id']}", json=body)
        assert response.status_code == 200
        updated = response.json()
        assert updated["name"] == "Óleo do motor (sintético)"
        kept, added = updated["schedules"]
        assert (kept["id"], kept["created_on"], kept["every_km"]) == (
            original["id"],
            "2026-11-09",
            5_000,
        )
        assert added["id"] not in (None, original["id"])
        assert added["created_on"] == "2026-12-01"

    def test_update_can_remove_a_schedule(self, client, api, car):
        item = api.item("Óleo do motor", EVERY_7500_KM, EVERY_6_MONTHS)
        body = {"name": item["name"], "schedules": [item["schedules"][1]]}
        updated = client.put(f"/api/items/{item['id']}", json=body).json()
        assert [s["id"] for s in updated["schedules"]] == [sid(item, 1)]

    def test_schedule_with_an_unknown_id_is_treated_as_new(self, client, api, car):
        item = api.item("Óleo do motor")
        body = {"name": item["name"], "schedules": [{**EVERY_7500_KM, "id": "forged"}]}
        updated = client.put(f"/api/items/{item['id']}", json=body).json()
        assert updated["schedules"][0]["id"] != "forged"

    def test_editing_an_interval_applies_to_the_current_cycle(self, client, api, car):
        item = api.item("Óleo do motor", {**EVERY_7500_KM, "baseline_km": 88_000})
        assert api.status(sid(item))["status"] == "ok"  # due at 95,500
        body = {"name": item["name"], "schedules": [{**item["schedules"][0], "every_km": 5_000}]}
        client.put(f"/api/items/{item['id']}", json=body)
        assert api.status(sid(item))["status"] == "due"  # now due at 93,000

    def test_delete_an_unused_item_removes_it(self, client, api, car):
        item = api.item("Óleo do motor", EVERY_7500_KM)
        response = client.delete(f"/api/items/{item['id']}")
        assert response.json() == {"archived": False}
        assert client.get("/api/items?include_archived=true").json() == []
        assert client.get(f"/api/items/{item['id']}").status_code == 404

    def test_delete_an_item_with_history_archives_it(self, client, api, car):
        item = api.item("Óleo do motor", EVERY_7500_KM)
        api.maint("2026-11-05", 93_100, item["id"])
        response = client.delete(f"/api/items/{item['id']}")
        assert response.json() == {"archived": True}
        assert client.get("/api/items").json() == []
        archived = client.get("/api/items?include_archived=true").json()
        assert [(i["id"], i["archived"]) for i in archived] == [(item["id"], True)]
        # No more notifications, but the history keeps its name.
        assert api.dashboard()["statuses"] == []
        assert client.get("/api/history").json()[0]["item_names"] == ["Óleo do motor"]

    def test_item_with_only_a_skip_is_also_archived(self, client, api, car):
        item = api.item("Óleo do motor", {**EVERY_7500_KM, "baseline_km": 93_000})
        assert api.action(item, "skip").status_code == 201
        assert client.delete(f"/api/items/{item['id']}").json() == {"archived": True}

    def test_restore_an_archived_item(self, client, api, car):
        item = api.item("Óleo do motor", EVERY_7500_KM)
        api.maint("2026-11-05", 93_100, item["id"])
        client.delete(f"/api/items/{item['id']}")
        response = client.post(f"/api/items/{item['id']}/restore")
        assert response.status_code == 200
        assert response.json()["archived"] is False
        assert [i["id"] for i in client.get("/api/items").json()] == [item["id"]]
        assert api.status(sid(item))["status"] == "ok"

    def test_unknown_item_is_404(self, client, car):
        assert client.get("/api/items/nope").status_code == 404
        assert client.put("/api/items/nope", json={"name": "X"}).status_code == 404
        assert client.delete("/api/items/nope").status_code == 404
        assert client.post("/api/items/nope/restore").status_code == 404


class TestMaintenance:
    def test_create_and_list(self, client, api, car):
        oil = api.item("Óleo do motor", EVERY_7500_KM)
        record = api.maint(
            "2026-11-05",
            93_100,
            oil["id"],
            cost_total=6_800,
            shop="トヨタモビリティ東京",
            notes="0W-20",
        )
        assert record["cost_total"] == 6_800
        assert record["shop"] == "トヨタモビリティ東京"
        assert client.get("/api/maintenance").json() == [record]

    def test_record_moves_the_current_km(self, api, car):
        oil = api.item("Óleo do motor", EVERY_7500_KM)
        api.maint("2026-11-05", 93_100, oil["id"])
        d = api.dashboard()
        assert (d["current_km"], d["last_reading_date"]) == (93_100, "2026-11-05")

    def test_unscheduled_work_uses_an_item_without_schedules(self, client, api, car):
        battery = api.item("Bateria trocada na estrada", jp_term="バッテリー交換")
        api.maint("2026-11-05", 93_100, battery["id"], cost_total=15_000)
        entry = client.get("/api/history").json()[0]
        assert entry["item_names"] == ["Bateria trocada na estrada"]
        assert api.dashboard()["notifications"] == []

    def test_needs_at_least_one_item(self, client, car):
        body = {"date": "2026-11-05", "km": 93_100, "item_ids": []}
        assert client.post("/api/maintenance", json=body).status_code == 422

    def test_unknown_item_is_rejected(self, client, car):
        body = {"date": "2026-11-05", "km": 93_100, "item_ids": ["nope"]}
        response = client.post("/api/maintenance", json=body)
        assert response.status_code == 422
        assert "não existe" in response.json()["detail"]

    def test_repeated_item_is_rejected(self, client, api, car):
        oil = api.item("Óleo do motor")
        body = {"date": "2026-11-05", "km": 93_100, "item_ids": [oil["id"], oil["id"]]}
        response = client.post("/api/maintenance", json=body)
        assert response.status_code == 422
        assert "repetido" in response.json()["detail"]

    def test_follows_the_km_order_rule(self, client, api, car):
        oil = api.item("Óleo do motor")
        api.fuel("2026-11-05", 93_400)
        body = {"date": "2026-11-08", "km": 93_300, "item_ids": [oil["id"]]}
        response = client.post("/api/maintenance", json=body)
        assert response.status_code == 422
        assert "93.400 km" in response.json()["detail"]

    def test_future_date_is_rejected(self, client, api, car):
        oil = api.item("Óleo do motor")
        body = {"date": "2026-11-10", "km": 93_100, "item_ids": [oil["id"]]}
        assert client.post("/api/maintenance", json=body).status_code == 422

    def test_update(self, client, api, car):
        oil = api.item("Óleo do motor")
        filt = api.item("Filtro de óleo")
        record = api.maint("2026-11-05", 93_100, oil["id"])
        body = {
            "date": "2026-11-06",
            "km": 93_150,
            "item_ids": [oil["id"], filt["id"]],
            "cost_total": 9_900,
        }
        response = client.put(f"/api/maintenance/{record['id']}", json=body)
        assert response.status_code == 200
        stored = client.get("/api/maintenance").json()[0]
        assert stored["id"] == record["id"]
        assert (stored["date"], stored["km"], stored["cost_total"]) == ("2026-11-06", 93_150, 9_900)
        assert stored["item_ids"] == [oil["id"], filt["id"]]

    def test_update_validates_like_create(self, client, api, car):
        oil = api.item("Óleo do motor")
        record = api.maint("2026-11-05", 93_100, oil["id"])
        api.fuel("2026-11-08", 93_500)
        url = f"/api/maintenance/{record['id']}"
        too_high = {"date": "2026-11-05", "km": 93_600, "item_ids": [oil["id"]]}
        assert client.put(url, json=too_high).status_code == 422
        ghost = {"date": "2026-11-05", "km": 93_100, "item_ids": ["nope"]}
        assert client.put(url, json=ghost).status_code == 422

    def test_delete(self, client, api, car):
        oil = api.item("Óleo do motor")
        record = api.maint("2026-11-05", 93_100, oil["id"])
        assert client.delete(f"/api/maintenance/{record['id']}").status_code == 204
        assert client.get("/api/maintenance").json() == []
        assert api.dashboard()["current_km"] == 93_000

    def test_unknown_record_is_404(self, client, api, car):
        oil = api.item("Óleo do motor")
        body = {"date": "2026-11-05", "km": 93_100, "item_ids": [oil["id"]]}
        assert client.put("/api/maintenance/nope", json=body).status_code == 404
        assert client.delete("/api/maintenance/nope").status_code == 404
