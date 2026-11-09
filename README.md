# Car Maintenance

Personal web app that shows which maintenance the car needs now, from the km
logged at each fill-up. See [SPEC.md](SPEC.md) for the rules.

## Run locally

Needs Docker, [uv](https://docs.astral.sh/uv/) and Node 22.

```bash
make api        # DynamoDB Local (Docker, port 8001) + API on http://localhost:8000
make web        # front end on http://localhost:5173 (in a second terminal)
make seed       # wipe the car and load the 2014 Prius with its maintenance items
make seed-demo  # same, plus fake history so every colour shows up
```

First time only: `cd frontend && npm install`.

## Tests

```bash
make test          # everything below
make test-unit     # status rules, no Docker needed
make test-feature  # the API against DynamoDB Local
make check-web     # front-end type check and build (there are no UI tests)
```

## Layout

| Path | What |
|---|---|
| `backend/app/engine.py` | The status rules: pure functions, no I/O |
| `backend/app/main.py` | HTTP API (FastAPI) |
| `backend/app/store.py` | DynamoDB storage, one table |
| `backend/app/seed.py` | Prius seed and demo history |
| `backend/tests/unit` | Unit tests for the rules |
| `backend/tests/feature` | API tests against DynamoDB Local |
| `frontend/` | Vue 3 app (pt-BR, mobile first) |

There is no login yet. Do not deploy the API before adding it.
