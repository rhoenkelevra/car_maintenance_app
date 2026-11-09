# Local development. DynamoDB Local runs in Docker on port 8001.
export DYNAMODB_ENDPOINT ?= http://localhost:8001
export TABLE_NAME ?= car_maintenance
export ENABLE_DEV_SEED ?= 1

.PHONY: db api web seed seed-demo test test-unit test-feature check-web

db:            ## start DynamoDB Local
	docker compose up -d dynamodb

api: db        ## run the API on http://localhost:8000
	cd backend && uv run uvicorn app.main:app --reload --port 8000

web:           ## run the front end on http://localhost:5173
	cd frontend && npm run dev

seed:          ## wipe the car and load the Prius seed (no history)
	curl -fsS -X POST "http://localhost:8000/api/dev/seed" && echo

seed-demo:     ## wipe the car and load the seed plus fake history
	curl -fsS -X POST "http://localhost:8000/api/dev/seed?demo=true" && echo

test-unit:     ## pure logic, no Docker needed
	cd backend && uv run pytest tests/unit -q

test-feature: db   ## API against DynamoDB Local
	cd backend && uv run pytest tests/feature -q

check-web:     ## type check and production build of the front end
	cd frontend && npm run build

test: test-unit test-feature check-web
