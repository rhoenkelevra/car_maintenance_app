"""Feature tests: the real API against DynamoDB Local, one fresh table per test.

Start the database first with `make db` (Docker). "Today" is a clock the test
controls, so flows can move through time.
"""

from __future__ import annotations

import os
import socket
import uuid
from datetime import date
from urllib.parse import urlparse

import pytest
from fastapi.testclient import TestClient

ENDPOINT = os.environ.setdefault("DYNAMODB_ENDPOINT", "http://localhost:8001")

from app.main import app, get_store, get_today  # noqa: E402
from app.store import Store, ensure_table, get_resource  # noqa: E402

TODAY = date(2026, 11, 9)


@pytest.fixture(scope="session")
def dynamodb():
    url = urlparse(ENDPOINT)
    try:
        socket.create_connection((url.hostname, url.port), timeout=2).close()
    except OSError:
        pytest.exit(
            f"DynamoDB Local is not reachable at {ENDPOINT}. Start it with `make db`.",
            returncode=1,
        )
    return get_resource()


@pytest.fixture
def table(dynamodb):
    table = ensure_table(dynamodb, f"test_{uuid.uuid4().hex}")
    yield table
    table.delete()


class Clock:
    def __init__(self) -> None:
        self.today = TODAY

    def set(self, iso: str) -> None:
        self.today = date.fromisoformat(iso)


@pytest.fixture
def clock() -> Clock:
    return Clock()


@pytest.fixture
def client(table, clock):
    app.dependency_overrides[get_store] = lambda: Store(table)
    app.dependency_overrides[get_today] = lambda: clock.today
    yield TestClient(app)
    app.dependency_overrides.clear()


class Api:
    """Thin helper over the HTTP client: creates things and asserts success."""

    def __init__(self, client: TestClient, clock: Clock):
        self.client = client
        self.clock = clock

    def put_car(self, **overrides) -> dict:
        body = {
            "maker": "Toyota",
            "model": "Prius",
            "start_km": 93_000,
            "start_date": "2026-11-01",
            **overrides,
        }
        response = self.client.put("/api/car", json=body)
        assert response.status_code == 200, response.text
        return response.json()

    def item(self, name: str = "Óleo do motor", *schedules: dict, **fields) -> dict:
        body = {"name": name, "schedules": list(schedules), **fields}
        response = self.client.post("/api/items", json=body)
        assert response.status_code == 201, response.text
        return response.json()

    def fuel(self, day: str, km: int, **fields) -> dict:
        response = self.client.post("/api/fuel", json={"date": day, "km": km, **fields})
        assert response.status_code == 201, response.text
        return response.json()

    def odo(self, day: str, km: int) -> dict:
        response = self.client.post("/api/odometer", json={"date": day, "km": km})
        assert response.status_code == 201, response.text
        return response.json()

    def maint(self, day: str, km: int, *item_ids: str, **fields) -> dict:
        body = {"date": day, "km": km, "item_ids": list(item_ids), **fields}
        response = self.client.post("/api/maintenance", json=body)
        assert response.status_code == 201, response.text
        return response.json()

    def dashboard(self) -> dict:
        response = self.client.get("/api/dashboard")
        assert response.status_code == 200, response.text
        return response.json()

    def status(self, schedule_id: str) -> dict:
        for status in self.dashboard()["statuses"]:
            if status["schedule_id"] == schedule_id:
                return status
        raise AssertionError(f"schedule {schedule_id} not in the dashboard")

    def notified(self) -> dict[str, str]:
        """Schedule id -> status for every row of the notification table."""
        return {n["schedule_id"]: n["status"] for n in self.dashboard()["notifications"]}

    def action(self, item: dict, name: str, body: dict | None = None, schedule: int = 0):
        sid = item["schedules"][schedule]["id"]
        return self.client.post(f"/api/items/{item['id']}/schedules/{sid}/{name}", json=body or {})


@pytest.fixture
def api(client, clock) -> Api:
    return Api(client, clock)


@pytest.fixture
def car(api) -> dict:
    """A registered car: 93,000 km on 2026-11-01. Today is 2026-11-09."""
    return api.put_car()


def trigger(status: dict, kind: str) -> dict:
    for t in status["triggers"]:
        if t["kind"] == kind:
            return t
    raise AssertionError(f"no {kind} trigger in {status['triggers']}")


def sid(item: dict, index: int = 0) -> str:
    return item["schedules"][index]["id"]


EVERY_7500_KM = {"type": "interval", "every_km": 7_500}
EVERY_6_MONTHS = {"type": "interval", "every_months": 6}
