# Car Maintenance — Spec v1

Status: v1 built. This file describes what the code does.

## 1. Purpose

A personal web app that tells me which maintenance my car needs now. I log the
odometer when I fuel up; the app compares km, dates and fill-up counts against
my schedules and shows a table of pending items at the top of the home screen.
An item only leaves the table when I register the maintenance (or explicitly
skip or snooze it).

## 2. Scope

**In v1**

- One car, one user. Every record carries a `car_id` so a second car is not a rewrite.
- CRUD for: car, items and their schedules, fuel logs, odometer readings, maintenance records.
- Notification table (computed, never stored), with skip and snooze.
- Km-based date projection ("~3 semanas").
- Full JSON export.
- UI in pt-BR, mobile first, responsive. Online only.
- Seed data for the 2014 Prius (section 11).
- Unit and feature tests for the back end (section 10). No UI tests.

**Later (not in v1)**

- Login (required before the first AWS deploy, see section 9).
- Stats: km/L, cost per km, monthly spend. The fuel fields needed are already stored.
- Receipt photos (S3), push or email notifications, presets, multiple cars, offline mode.

## 3. Concepts

| Concept | What it is |
|---|---|
| **Car** | Maker, model, model code, year, plate, tank capacity (L), starting km, starting date, 車検 expiry (informational), notes. |
| **Item** | One thing that gets maintained, e.g. "Óleo do motor". Has a pt-BR name, a free-text JP term (エンジンオイル交換), notes, and zero or more schedules. An item with no schedule is valid (used for unscheduled work). |
| **Schedule** | A rule saying when an item is due. Belongs to one item. |
| **Fuel log** | Date, km, litres, total price (¥), full tank, fuel type, station, notes. |
| **Odometer reading** | Date, km, note. A plain "update km" entry. |
| **Maintenance record** | Date, km, one or more items, total cost (¥), shop, notes. One shop visit can cover several items. |
| **Schedule event** | A skip or a snooze on one schedule, kept in the history. |

## 4. Schedule rules

### 4.1 Schedule types

| Type | Example | Triggers |
|---|---|---|
| **Interval** | Oil every 7,500 km or 6 months | Any combination of `every_km`, `every_months`, `every_fillups`. Whichever comes first. |
| **Yearly pinned** | 自動車税 every May | One or more months, optional day (default 1). |
| **One-time** | Spark plugs at 100,000 km | `at_km` and/or `on_date`. Whichever comes first. |

### 4.2 Anchor (interval schedules)

- `actual` (default): the next cycle counts from when the maintenance was really done. Oil done at 6,400 km with a 6,000 km interval is next due at 12,400 km.
- `fixed`: due points sit on a fixed grid from a first due date or km (車検: 2027-03-20, then every 24 months), regardless of when it was done.

Yearly pinned schedules are always fixed.

### 4.3 Baseline

The baseline of an `actual` schedule is the most recent of:

1. a maintenance record that includes the schedule's item (its date and km);
2. a skip event on the schedule;
3. a manual baseline set on the schedule ("informar última vez" or "começar a contar de hoje").

If none exists the schedule has **no history** and shows as a grey row until I
give it a baseline. Fixed, yearly pinned and one-time schedules need no baseline.

Fill-ups are counted as the number of fuel logs after the baseline. Every fuel
log counts, partial or full.

### 4.4 Completion

- Registering a maintenance record resets every `actual` schedule of the items in it. Registering early is allowed and simply restarts the cycle.
- A fixed, yearly pinned or one-time due point is cleared only by a record made at or after that due point's yellow threshold. An oil change at 94,000 km does not clear "oil at 100,000 km".
- A cleared one-time schedule is finished: it leaves the table and stays in the history.

### 4.5 Status and colours

| Status | Colour | When |
|---|---|---|
| `ok` | none (not in the table) | Before the yellow threshold |
| `upcoming` | yellow | Within the lead before due |
| `due` | orange | At or past due |
| `overdue` | red | Past due by more than the overdue margin |
| `no_history` | grey | No baseline yet |

- Default lead and overdue margin are each **10% of the interval**, per trigger, with a minimum of 1 unit (1 km, 1 day, 1 fill-up). Oil at 7,500 km: yellow at 6,750, orange at 7,500, red at 8,250.
- For month intervals a month counts as 30 days, so 6 months gives 18 days and 24 months gives 72 days.
- For fill-ups the lead is capped at one less than the interval: "every 3 fill-ups" is yellow at 2, orange at 3, red at 4.
- Yearly pinned schedules use 10% of the gap between pinned months: 36 days for one month a year, 18 days for two.
- One-time schedules have no interval: default lead and margin are 500 km and 30 days.
- All four values (`lead_km`, `lead_days`, `overdue_km`, `overdue_days`) can be overridden per schedule.
- With several triggers the schedule takes the worst status among them. The row shows which trigger is driving it and the remaining amount for each.

### 4.6 Skip and snooze

- **Skip this cycle** ("Pular"): acts as a completion for the baseline, with no maintenance record. Recorded as an event with an optional note. A schedule without history cannot be skipped; a fixed, yearly or one-time due point can only be skipped from its yellow threshold on.
- **Snooze** ("Adiar"): replaces the due point of the current cycle with a new km and/or date ("check again in 5,000 km"). Only the targets given apply: snoozing to a km drops the date trigger for that cycle. Yellow, orange and red then apply relative to the new point. Only a schedule that is yellow, orange or red can be snoozed, and the target must be beyond the current km or after today. Ended by the next completion. Recorded as an event.
- Both can be undone by deleting the event from the history.

### 4.7 Current km and projection

- **Current km** is the highest km among fuel logs, odometer readings and maintenance records. Statuses use only this logged value.
- **Pace** is km per day over the last 90 days of readings (all readings if fewer; needs two readings at least 7 days apart).
- **Projection:** for a km trigger, estimated due date = today + remaining km ÷ pace. Shown as a hint on the row.
- **Stale odometer:** if the last reading is over 30 days old, the home screen shows "Atualize o km" with the estimated km as a hint.

## 5. Screens (pt-BR)

| Screen | Content |
|---|---|
| **Início** | Notification table on top, sorted red → orange → yellow → grey. Current km, stale-odometer banner, and buttons "+ Abastecimento", "+ Manutenção", "Atualizar km". |
| **Abastecimentos** | List and form. Date defaults to today, fuel type to "regular", full tank to yes. Only date and km are required. |
| **Manutenções** | History (records, skips, snoozes) and form. The form multi-selects items; opened from a notification it comes with that item selected. A new item can be created inline for unscheduled work. |
| **Itens** | Every item with the status of each schedule, including `ok` ones. Item form with a schedules editor. Items with history are archived, not deleted. |
| **Carro** | Car details, the list of plain km readings (a wrong one is deleted here and typed again), and the JSON export button. |

Each notification row shows: colour, item name, JP term, the reason ("faltam
400 km", "vencido há 12 dias"), the projection, and the actions **Registrar**,
**Adiar**, **Pular**. Grey rows show **Informar última vez** and **Começar a
contar de hoje** instead.

## 6. Validation and edge cases

- **Km order:** an entry's km must be ≥ the highest km logged on an earlier date, ≤ the lowest km logged on a later date, and ≥ the car's starting km. Violations are rejected, which also allows backdated entries that fit. Entries on the same date do not constrain each other.
- **No future dates:** fuel logs, odometer readings and maintenance records cannot be dated after today.
- **Car starting km** cannot be raised above a km already logged.
- **Edits and deletes** of any log are allowed; every status is recomputed from the logs on each request.
- **Editing a schedule** (7,500 → 5,000 km) applies to the current cycle immediately.
- **Dates** are `YYYY-MM-DD`; "today" is evaluated in Asia/Tokyo.
- **Units:** km (integer), litres (decimal), yen (integer).
- **車検 expiry** on the car is informational. The notification comes from the seeded 車検 schedule; I edit the car field by hand after each inspection.

## 7. Data model (DynamoDB)

One on-demand table. Partition key `PK = CAR#<car_id>`; one Query loads the
whole car, which is small enough to compute everything in memory.

| SK | Entity | Main attributes |
|---|---|---|
| `META` | Car | maker, model, model_code, year, plate, tank_l, start_km, start_date, shaken_expiry, notes |
| `ITEM#<id>` | Item | name, jp_term, notes, archived, `schedules[]` (embedded) |
| `FUEL#<id>` | Fuel log | date, km, litres, price_total, full_tank, fuel_type, station, notes |
| `ODO#<id>` | Odometer reading | date, km, note |
| `MAINT#<id>` | Maintenance record | date, km, item_ids[], cost_total, shop, notes |
| `EVENT#<id>` | Schedule event | type (`skip` or `snooze`), item_id, schedule_id, date, km, until_km, until_date, note, created_at |

Sort keys carry no date, so editing an entry's date is a plain overwrite;
sorting happens in memory.

Embedded schedule: `id`, `type` (`interval`, `yearly`, `one_time`), `anchor`,
`every_km`, `every_months`, `every_fillups`, `months[]`, `day`, `at_km`,
`on_date`, `first_due_km`, `first_due_date`, `baseline_km`, `baseline_date`,
`lead_km`, `lead_days`, `overdue_km`, `overdue_days`, `active`, `created_on`
(yearly schedules start counting from this date).

## 8. API

REST, JSON, under `/api`.

| Method and path | Purpose |
|---|---|
| `GET /dashboard` | Current km, estimated km, stale flag, notifications |
| `GET`, `PUT /car` | Car details |
| `GET`, `POST /items`; `GET`, `PUT`, `DELETE /items/{id}` | Items with embedded schedules (delete archives when history exists; `?include_archived=true` lists them) |
| `POST /items/{id}/restore` | Bring an archived item back |
| `POST /items/{id}/schedules/{sid}/skip` | Skip this cycle |
| `POST /items/{id}/schedules/{sid}/snooze` | Snooze to a km and/or date |
| `POST /items/{id}/schedules/{sid}/baseline` | Set the last-done km and date, or start from today |
| `GET`, `POST /fuel`; `PUT`, `DELETE /fuel/{id}` | Fuel logs |
| `GET`, `POST /odometer`; `PUT`, `DELETE /odometer/{id}` | Odometer readings |
| `GET`, `POST /maintenance`; `PUT`, `DELETE /maintenance/{id}` | Maintenance records |
| `DELETE /events/{id}` | Undo a skip or a snooze |
| `GET /history` | Records, skips and snoozes merged by date |
| `GET /export` | Everything as one JSON document |
| `POST /dev/seed` | Wipe the car and load seed data; `?demo=true` adds fake history. Only when `ENABLE_DEV_SEED=1` |

Errors come back as `{"detail": "<message in pt-BR>"}`: 422 for invalid data,
409 when the action does not apply (no car yet, nothing to skip or snooze),
404 for unknown ids.

## 9. Stack and deployment

- **Front end:** Vue 3, Vite, TypeScript, vue-router. Plain CSS, mobile first.
- **Back end:** Python, FastAPI, Pydantic, boto3. Runs on Lambda through an ASGI adapter.
- **Status engine:** a pure Python module with no I/O (inputs: car, items, logs, today; output: statuses), covered by unit tests. This is the core of the app.
- **Local development:** Vite dev server proxying `/api` to FastAPI under uvicorn, with DynamoDB Local running in Docker (docker compose).
- **AWS (later):** S3 and CloudFront for the front end; CloudFront routes `/api/*` to the Lambda so both share one origin. DynamoDB on-demand with point-in-time recovery.
- **Login:** none while running locally. Cognito with a single user goes in **before** the API is first deployed, because an unauthenticated API would be public.

## 10. Testing

All tests are back-end tests in pytest. `make test` runs everything:
`make test-unit` (no Docker needed), `make test-feature` (needs `make db`),
and the front-end type check and build.

**Unit tests** cover the pure logic with no I/O. "Today" is always passed in,
never read from the clock.

- Status engine, per schedule type: interval, yearly pinned, one-time.
- Threshold boundaries: the exact km, day and fill-up where a status changes to yellow, orange and red, including the 1-unit minimum and per-schedule overrides.
- Combined triggers taking the worst status.
- Anchors: `actual` versus `fixed`, and which baseline wins (record, skip, manual).
- Completion: early registration restarting a cycle; fixed and one-time due points cleared only from the yellow threshold on.
- Skip and snooze.
- Fill-up counting after a baseline.
- Current km, pace, projection, and the stale-odometer flag.
- Km order validation, including backdated entries.
- Date arithmetic: month ends (31 August + 6 months), leap years, and "today" in Asia/Tokyo.

**Feature tests** call the real API (FastAPI test client) against DynamoDB
Local in Docker, with a fresh table per test.

- CRUD and validation errors for every endpoint.
- Whole flows, for example: log fuel → the dashboard shows oil in yellow → register the maintenance → the row is gone.
- One maintenance record clearing several items.
- Editing and deleting old logs, with statuses recomputed.
- Grey row → set baseline → normal status.
- Skip, snooze, archive, export, and the seed loader.

**Not tested:** the UI. No component tests and no browser tests. The front end
only gets a type check and a production build as part of the same command, and
it stays thin: all rules live in the back end.

## 11. Seed data

**Car:** Toyota Prius (ZVW30), 2014, starting at 93,000 km, 車検 until
2027-03-20. Starting date, plate and tank capacity to be filled in.

Intervals use Toyota Japan's "severe use" values because most trips are under
8 km. All `actual` schedules start with no history (grey) except where noted.

| Item (pt-BR) | JP term | Schedule | Basis |
|---|---|---|---|
| Óleo do motor | エンジンオイル交換 | 7,500 km or 6 months | Toyota, severe |
| Filtro de óleo | オイルフィルター交換 | 7,500 km | Toyota, severe |
| Filtro de ar do motor | エアクリーナーエレメント交換 | 25,000 km | Toyota, severe |
| Fluido de freio | ブレーキフルード交換 | 24 months | Toyota |
| Líquido de arrefecimento do motor | 冷却水(スーパーLLC)交換 | 80,000 km or 48 months | Toyota (second and later changes) |
| Fluido do transeixo (e-CVT) | トランスミッションフルード交換 | 100,000 km, baseline 0 km | Toyota, severe |
| Velas de ignição | スパークプラグ交換 | One-time at 100,000 km | **Unconfirmed:** 100,000 or 200,000 km |
| Líquido do inversor | インバーター冷却水交換 | No schedule yet | **Unconfirmed:** Toyota says to ask the dealer |
| Bateria auxiliar 12V | 補機バッテリー交換 | 36 months | Toyota says 2–3 years |
| Filtro do ar-condicionado | エアコンフィルター交換 | 15,000 km | Toyota |
| Calibragem dos pneus | タイヤ空気圧点検 | 1 month | Common practice |
| Rodízio de pneus | タイヤローテーション | 5,000 km | Common practice |
| Palhetas do limpador | ワイパーゴム交換 | 12 months | Common practice |
| Vistoria (shaken) | 車検 | Fixed, 24 months, first due 2027-03-20 | Car's expiry date |
| Inspeção de 12 meses | 法定12ヶ月点検 | Fixed, 24 months, first due 2028-03-20 | Legal inspection between 車検 |
| Aditivo de combustível | 燃料添加剤 | 3 fill-ups or 5,000 km | Product label |
| Reaplicar coating | コーティング再施工 | 6 months (placeholder) | To be set |
| Imposto do automóvel | 自動車税 | Yearly in May, day 31 | Example of a pinned schedule |

A second, clearly fake **demo seed** adds fuel logs and maintenance history so
that all five statuses appear on screen during development.

## 12. Open points

1. Spark plug and inverter coolant intervals: confirm in the car's メンテナンスノート.
2. Coating interval and the car's starting date, plate and tank capacity.
