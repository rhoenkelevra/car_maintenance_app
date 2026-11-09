"""DynamoDB storage: one table, one partition per car.

Every row has PK = CAR#<car_id> and an SK naming the entity. A single Query
loads the whole car, which is small enough to work on in memory.
"""

from __future__ import annotations

import os
from decimal import Decimal
from functools import lru_cache
from typing import Any

import boto3
from boto3.dynamodb.conditions import Key

from .engine import Snapshot
from .models import Car, FuelLog, Item, MaintenanceRecord, OdometerReading, ScheduleEvent

CAR_ID = "main"

SK_CAR = "META"
PREFIX_ITEM = "ITEM#"
PREFIX_FUEL = "FUEL#"
PREFIX_ODO = "ODO#"
PREFIX_MAINT = "MAINT#"
PREFIX_EVENT = "EVENT#"


def table_name() -> str:
    return os.environ.get("TABLE_NAME", "car_maintenance")


def get_resource():
    endpoint = os.environ.get("DYNAMODB_ENDPOINT")
    if endpoint:
        # DynamoDB Local: credentials are required by the SDK but not checked.
        return boto3.resource(
            "dynamodb",
            endpoint_url=endpoint,
            region_name="ap-northeast-1",
            aws_access_key_id="local",
            aws_secret_access_key="local",
        )
    return boto3.resource("dynamodb")


def ensure_table(resource, name: str):
    """Create the table when missing (local development and tests)."""
    client = resource.meta.client
    try:
        resource.create_table(
            TableName=name,
            KeySchema=[
                {"AttributeName": "PK", "KeyType": "HASH"},
                {"AttributeName": "SK", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "PK", "AttributeType": "S"},
                {"AttributeName": "SK", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        client.get_waiter("table_exists").wait(TableName=name)
    except client.exceptions.ResourceInUseException:
        pass
    return resource.Table(name)


@lru_cache(maxsize=1)
def get_table():
    resource = get_resource()
    if os.environ.get("DYNAMODB_ENDPOINT"):
        return ensure_table(resource, table_name())
    return resource.Table(table_name())


def _to_db(value: Any) -> Any:
    if isinstance(value, float):
        return Decimal(str(value))
    if isinstance(value, dict):
        return {k: _to_db(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_to_db(v) for v in value]
    return value


def _from_db(value: Any) -> Any:
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral_value() else float(value)
    if isinstance(value, dict):
        return {k: _from_db(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_from_db(v) for v in value]
    return value


class Store:
    def __init__(self, table, car_id: str = CAR_ID):
        self.table = table
        self.pk = f"CAR#{car_id}"

    # --- raw rows ---

    def _rows(self) -> list[dict]:
        rows: list[dict] = []
        kwargs: dict[str, Any] = {"KeyConditionExpression": Key("PK").eq(self.pk)}
        while True:
            page = self.table.query(**kwargs)
            rows += page["Items"]
            if "LastEvaluatedKey" not in page:
                return [_from_db(r) for r in rows]
            kwargs["ExclusiveStartKey"] = page["LastEvaluatedKey"]

    def _put(self, sk: str, model) -> None:
        row = _to_db(model.model_dump(mode="json"))
        self.table.put_item(Item={**row, "PK": self.pk, "SK": sk})

    def _delete(self, sk: str) -> None:
        self.table.delete_item(Key={"PK": self.pk, "SK": sk})

    # --- reads ---

    def load(self) -> Snapshot | None:
        """Everything for the car, or None when the car is not registered yet."""
        car = None
        items, fuel, odometer, maintenance, events = [], [], [], [], []
        for row in self._rows():
            sk = row["SK"]
            if sk == SK_CAR:
                car = Car.model_validate(row)
            elif sk.startswith(PREFIX_ITEM):
                items.append(Item.model_validate(row))
            elif sk.startswith(PREFIX_FUEL):
                fuel.append(FuelLog.model_validate(row))
            elif sk.startswith(PREFIX_ODO):
                odometer.append(OdometerReading.model_validate(row))
            elif sk.startswith(PREFIX_MAINT):
                maintenance.append(MaintenanceRecord.model_validate(row))
            elif sk.startswith(PREFIX_EVENT):
                events.append(ScheduleEvent.model_validate(row))
        if car is None:
            return None
        items.sort(key=lambda i: i.name.lower())
        fuel.sort(key=lambda f: (f.date, f.km), reverse=True)
        odometer.sort(key=lambda o: (o.date, o.km), reverse=True)
        maintenance.sort(key=lambda m: (m.date, m.km), reverse=True)
        events.sort(key=lambda e: (e.date, e.created_at), reverse=True)
        return Snapshot(car, items, fuel, odometer, maintenance, events)

    # --- writes ---

    def put_car(self, car: Car) -> None:
        self._put(SK_CAR, car)

    def put_item(self, item: Item) -> None:
        self._put(PREFIX_ITEM + item.id, item)

    def delete_item(self, item_id: str) -> None:
        self._delete(PREFIX_ITEM + item_id)

    def put_fuel(self, log: FuelLog) -> None:
        self._put(PREFIX_FUEL + log.id, log)

    def delete_fuel(self, log_id: str) -> None:
        self._delete(PREFIX_FUEL + log_id)

    def put_odometer(self, reading: OdometerReading) -> None:
        self._put(PREFIX_ODO + reading.id, reading)

    def delete_odometer(self, reading_id: str) -> None:
        self._delete(PREFIX_ODO + reading_id)

    def put_maintenance(self, record: MaintenanceRecord) -> None:
        self._put(PREFIX_MAINT + record.id, record)

    def delete_maintenance(self, record_id: str) -> None:
        self._delete(PREFIX_MAINT + record_id)

    def put_event(self, event: ScheduleEvent) -> None:
        self._put(PREFIX_EVENT + event.id, event)

    def delete_event(self, event_id: str) -> None:
        self._delete(PREFIX_EVENT + event_id)

    def wipe(self) -> int:
        """Delete every row of this car. Returns how many were removed."""
        rows = self._rows()
        with self.table.batch_writer() as batch:
            for row in rows:
                batch.delete_item(Key={"PK": row["PK"], "SK": row["SK"]})
        return len(rows)
