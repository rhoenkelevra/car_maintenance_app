"""CRUD and validation for the car, fuel logs and odometer readings."""

import pytest

from .conftest import EVERY_7500_KM


class TestCar:
    def test_there_is_no_car_at_first(self, client):
        response = client.get("/api/car")
        assert response.status_code == 200
        assert response.json() is None

    @pytest.mark.parametrize(
        "method, path",
        [
            ("get", "/api/dashboard"),
            ("get", "/api/items"),
            ("get", "/api/fuel"),
            ("get", "/api/odometer"),
            ("get", "/api/maintenance"),
            ("get", "/api/history"),
            ("get", "/api/export"),
        ],
    )
    def test_everything_else_waits_for_the_car(self, client, method, path):
        response = getattr(client, method)(path)
        assert response.status_code == 409
        assert response.json()["detail"] == "Cadastre o carro primeiro."

    def test_cannot_log_fuel_without_a_car(self, client):
        response = client.post("/api/fuel", json={"date": "2026-11-09", "km": 93_100})
        assert response.status_code == 409

    def test_register_and_read_the_car(self, client, api):
        saved = api.put_car(
            model_code="ZVW30",
            year=2014,
            plate="品川 300 あ 12-34",
            tank_l=45,
            shaken_expiry="2027-03-20",
            notes="Comprado usado",
        )
        assert client.get("/api/car").json() == saved
        assert saved["shaken_expiry"] == "2027-03-20"
        assert saved["plate"] == "品川 300 あ 12-34"
        assert saved["tank_l"] == 45

    def test_update_the_car(self, client, api, car):
        api.put_car(plate="ABC-1234", start_km=92_500)
        assert client.get("/api/car").json()["plate"] == "ABC-1234"
        assert api.dashboard()["current_km"] == 92_500

    @pytest.mark.parametrize(
        "bad",
        [
            {"maker": ""},
            {"start_km": -1},
            {"start_date": "not-a-date"},
            {"year": 1800},
            {"tank_l": 0},
        ],
    )
    def test_rejects_invalid_car_data(self, client, bad):
        body = {"maker": "Toyota", "model": "Prius", "start_km": 93_000, "start_date": "2026-11-01"}
        response = client.put("/api/car", json={**body, **bad})
        assert response.status_code == 422
        assert isinstance(response.json()["detail"], str)

    def test_start_km_cannot_exceed_a_logged_km(self, client, api, car):
        api.fuel("2026-11-05", 93_400)
        body = {"maker": "Toyota", "model": "Prius", "start_km": 93_500, "start_date": "2026-11-01"}
        response = client.put("/api/car", json=body)
        assert response.status_code == 422
        assert "93.400 km" in response.json()["detail"]


class TestFuel:
    def test_create_with_only_date_and_km(self, client, api, car):
        log = api.fuel("2026-11-09", 93_400)
        assert log["fuel_type"] == "regular"
        assert log["full_tank"] is True
        assert log["litres"] is None and log["price_total"] is None
        assert client.get("/api/fuel").json() == [log]

    def test_extra_fields_round_trip(self, client, api, car):
        log = api.fuel(
            "2026-11-09",
            93_400,
            litres=28.45,
            price_total=4_893,
            full_tank=False,
            station="ENEOS 品川",
            notes="meio tanque",
        )
        stored = client.get("/api/fuel").json()[0]
        assert stored == log
        assert stored["litres"] == 28.45
        assert stored["price_total"] == 4_893
        assert stored["station"] == "ENEOS 品川"

    def test_list_is_newest_first(self, client, api, car):
        api.fuel("2026-11-03", 93_200)
        api.fuel("2026-11-09", 93_900)
        api.fuel("2026-11-06", 93_500)
        assert [f["km"] for f in client.get("/api/fuel").json()] == [93_900, 93_500, 93_200]

    def test_fuel_log_moves_the_current_km(self, api, car):
        api.fuel("2026-11-09", 93_400)
        d = api.dashboard()
        assert (d["current_km"], d["last_reading_date"]) == (93_400, "2026-11-09")

    def test_km_lower_than_already_registered_is_rejected(self, client, api, car):
        api.fuel("2026-11-05", 93_400)
        response = client.post("/api/fuel", json={"date": "2026-11-09", "km": 93_399})
        assert response.status_code == 422
        assert "93.400 km" in response.json()["detail"]
        assert len(client.get("/api/fuel").json()) == 1

    def test_km_below_the_car_start_is_rejected(self, client, car):
        response = client.post("/api/fuel", json={"date": "2026-11-09", "km": 92_999})
        assert response.status_code == 422
        assert "km inicial" in response.json()["detail"]

    def test_backdated_entry_that_fits_is_accepted(self, api, car):
        api.fuel("2026-11-03", 93_200)
        api.fuel("2026-11-09", 93_900)
        assert api.fuel("2026-11-06", 93_500)["km"] == 93_500

    def test_backdated_entry_above_a_later_one_is_rejected(self, client, api, car):
        api.fuel("2026-11-03", 93_200)
        api.fuel("2026-11-09", 93_900)
        response = client.post("/api/fuel", json={"date": "2026-11-06", "km": 93_901})
        assert response.status_code == 422
        assert "93.900 km" in response.json()["detail"]

    def test_the_order_is_checked_across_every_kind_of_log(self, client, api, car):
        item = api.item("Óleo do motor", EVERY_7500_KM)
        api.odo("2026-11-04", 93_300)
        api.maint("2026-11-06", 93_600, item["id"])
        assert client.post("/api/fuel", json={"date": "2026-11-05", "km": 93_250}).status_code == 422
        assert client.post("/api/fuel", json={"date": "2026-11-05", "km": 93_650}).status_code == 422
        assert client.post("/api/fuel", json={"date": "2026-11-05", "km": 93_450}).status_code == 201

    def test_future_date_is_rejected(self, client, car):
        response = client.post("/api/fuel", json={"date": "2026-11-10", "km": 93_400})
        assert response.status_code == 422
        assert "futuro" in response.json()["detail"]

    @pytest.mark.parametrize(
        "body",
        [
            {"date": "2026-11-09"},
            {"km": 93_400},
            {"date": "2026-11-09", "km": -5},
            {"date": "2026-11-09", "km": 93_400, "litres": 0},
            {"date": "2026-11-09", "km": 93_400, "price_total": -1},
            {"date": "09/11/2026", "km": 93_400},
        ],
    )
    def test_rejects_invalid_bodies_with_a_readable_message(self, client, car, body):
        response = client.post("/api/fuel", json=body)
        assert response.status_code == 422
        assert isinstance(response.json()["detail"], str)

    def test_update(self, client, api, car):
        log = api.fuel("2026-11-05", 93_400)
        response = client.put(
            f"/api/fuel/{log['id']}", json={"date": "2026-11-06", "km": 93_450, "litres": 30}
        )
        assert response.status_code == 200
        assert client.get("/api/fuel").json() == [
            {**log, "date": "2026-11-06", "km": 93_450, "litres": 30}
        ]

    def test_update_is_not_blocked_by_its_own_old_value(self, client, api, car):
        # The typo case: 95,200 was meant to be 93,200.
        log = api.fuel("2026-11-05", 95_200)
        response = client.put(f"/api/fuel/{log['id']}", json={"date": "2026-11-05", "km": 93_200})
        assert response.status_code == 200
        assert api.dashboard()["current_km"] == 93_200

    def test_update_still_respects_the_neighbours(self, client, api, car):
        api.fuel("2026-11-03", 93_200)
        log = api.fuel("2026-11-05", 93_400)
        api.fuel("2026-11-07", 93_600)
        for km in (93_199, 93_601):
            response = client.put(f"/api/fuel/{log['id']}", json={"date": "2026-11-05", "km": km})
            assert response.status_code == 422

    def test_delete(self, client, api, car):
        api.fuel("2026-11-05", 93_400)
        log = api.fuel("2026-11-09", 93_900)
        assert client.delete(f"/api/fuel/{log['id']}").status_code == 204
        assert [f["km"] for f in client.get("/api/fuel").json()] == [93_400]
        assert api.dashboard()["current_km"] == 93_400

    def test_unknown_id_is_404(self, client, car):
        assert client.put("/api/fuel/nope", json={"date": "2026-11-09", "km": 93_400}).status_code == 404
        assert client.delete("/api/fuel/nope").status_code == 404


class TestOdometer:
    def test_create_list_update_delete(self, client, api, car):
        reading = api.odo("2026-11-08", 93_700)
        assert client.get("/api/odometer").json() == [{**reading, "note": ""}]
        assert api.dashboard()["current_km"] == 93_700

        response = client.put(
            f"/api/odometer/{reading['id']}",
            json={"date": "2026-11-08", "km": 93_750, "note": "conferido"},
        )
        assert response.status_code == 200
        assert client.get("/api/odometer").json()[0]["note"] == "conferido"
        assert api.dashboard()["current_km"] == 93_750

        assert client.delete(f"/api/odometer/{reading['id']}").status_code == 204
        assert client.get("/api/odometer").json() == []
        assert api.dashboard()["current_km"] == 93_000

    def test_follows_the_same_km_order_rule(self, client, api, car):
        api.fuel("2026-11-05", 93_400)
        response = client.post("/api/odometer", json={"date": "2026-11-09", "km": 93_300})
        assert response.status_code == 422

    def test_future_date_is_rejected(self, client, car):
        response = client.post("/api/odometer", json={"date": "2026-12-01", "km": 93_400})
        assert response.status_code == 422

    def test_unknown_id_is_404(self, client, car):
        assert client.delete("/api/odometer/nope").status_code == 404
        response = client.put("/api/odometer/nope", json={"date": "2026-11-09", "km": 93_400})
        assert response.status_code == 404


class TestDashboardBasics:
    def test_today_comes_from_the_server_clock(self, api, car, clock):
        assert api.dashboard()["today"] == "2026-11-09"
        clock.set("2027-01-02")
        assert api.dashboard()["today"] == "2027-01-02"

    def test_stale_odometer_after_30_days(self, api, car, clock):
        api.odo("2026-11-09", 93_800)
        clock.set("2026-12-09")
        assert api.dashboard()["stale"] is False
        clock.set("2026-12-10")
        d = api.dashboard()
        assert d["stale"] is True
        # 800 km in 8 days is 100 km a day; 31 days later the estimate is 96,900.
        assert d["pace_km_per_day"] == 100.0
        assert d["estimated_km"] == 96_900
        assert d["current_km"] == 93_800


class TestValidationMessages:
    """Every 422 carries one pt-BR sentence the form can show as is."""

    @pytest.mark.parametrize(
        "body, detail",
        [
            ({"date": "2026-11-09"}, "Km: campo obrigatório"),
            ({"km": 93_400}, "Data: campo obrigatório"),
            ({"date": "2026-11-09", "km": -5}, "Km: deve ser no mínimo 0"),
            ({"date": "2026-11-09", "km": "abc"}, "Km: número inválido"),
            ({"date": "2026-11-09", "km": 93_400, "litres": 0}, "Litros: deve ser maior que 0"),
            ({"date": "09/11/2026", "km": 93_400}, "Data: data inválida"),
        ],
    )
    def test_fuel_field_errors(self, client, car, body, detail):
        assert client.post("/api/fuel", json=body).json()["detail"] == detail

    def test_car_field_errors(self, client):
        body = {"maker": "", "model": "Prius", "start_km": 93_000, "start_date": "2026-11-01"}
        assert client.put("/api/car", json=body).json()["detail"] == "Marca: não pode ficar vazio"
        body = {"maker": "Toyota", "model": "Prius", "start_km": 93_000, "start_date": "2026-11-01"}
        response = client.put("/api/car", json={**body, "year": 1800})
        assert response.json()["detail"] == "Ano: deve ser no mínimo 1900"

    def test_maintenance_without_items(self, client, car):
        body = {"date": "2026-11-05", "km": 93_100, "item_ids": []}
        response = client.post("/api/maintenance", json=body)
        assert response.json()["detail"] == "Itens: escolha ao menos um"

    def test_schedule_errors_say_which_schedule(self, client, car):
        schedules = [{"type": "interval", "every_km": 7_500}, {"type": "yearly"}]
        response = client.post("/api/items", json={"name": "X", "schedules": schedules})
        assert response.json()["detail"] == "Agenda 2: Escolha ao menos um mês."
        schedules = [{"type": "interval", "every_km": 0}]
        response = client.post("/api/items", json={"name": "X", "schedules": schedules})
        assert response.json()["detail"] == "Agenda 1: Intervalo em km: deve ser maior que 0"

    def test_km_order_errors_use_pt_br_numbers(self, client, api, car):
        api.fuel("2026-11-05", 93_400)
        response = client.post("/api/fuel", json={"date": "2026-11-09", "km": 93_399})
        assert response.json()["detail"] == (
            "O km não pode ser menor que o já registrado antes dessa data (93.400 km)."
        )
