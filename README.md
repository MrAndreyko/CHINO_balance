# Hotel Room Balancing Service (v1 Bootstrap)

This repository contains a production-structured starter for a self-hosted hotel room-balancing platform.

## Stack

- **Backend**: Python, FastAPI, SQLAlchemy, Alembic
- **Database**: PostgreSQL
- **Frontend**: React (Vite scaffold)
- **Orchestration**: Docker Compose

> Scope of this bootstrap: structure, database setup, models, migrations, seed data, import pipelines, and local run flow.
> Not included yet: optimizer logic, PMS integrations, machine learning.

## Project Structure

```text
.
├── backend/
│   ├── app/
│   │   ├── api/v1/endpoints/
│   │   │   ├── health.py
│   │   │   └── imports.py
│   │   ├── core/config.py
│   │   ├── db/
│   │   ├── models/
│   │   ├── schemas/imports.py
│   │   ├── services/import_pipeline.py
│   │   └── main.py
│   ├── alembic/versions/
│   │   ├── 0001_initial_schema.py
│   │   └── 0002_import_jobs.py
│   ├── scripts/seed_defaults.py
│   ├── tests/test_import_pipeline.py
│   ├── alembic.ini
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
├── docker-compose.yml
└── .env.example
```

## Database Entities in v1

Core entities:
- rooms
- reservations
- reservation_requests
- request_code_rules
- inventory_overrides
- assignment_runs
- assignment_results
- weights_config
- compatibility_rules
- manual_overrides

Import pipeline entities:
- import_jobs
- import_job_errors

## Local Run Instructions

### 1) Configure environment

```bash
cp .env.example .env
```

### 2) Build and start services

```bash
docker compose up --build -d
```

### 3) Run migrations

```bash
docker compose exec backend alembic upgrade head
```

### 4) Seed default request codes and weights

```bash
docker compose exec backend python -m scripts.seed_defaults
```

### 5) Import APIs (preview + commit)

Supported datasets:
- `room_master`
- `request_code_rules`
- `reservations`
- `inventory_overrides`

Supported formats:
- CSV
- XLSX

Preview import (validation + row-level errors):

```bash
curl -X POST \
  -F "file=@./samples/rooms.csv" \
  http://localhost:8000/api/v1/imports/room_master/preview
```

Commit preview job:

```bash
curl -X POST http://localhost:8000/api/v1/imports/{job_id}/commit
```

Check import status/errors:

```bash
curl http://localhost:8000/api/v1/imports/{job_id}
```


### 7) Run assignment engine

Run types:
- `type-balance`
- `exact-room`

Trigger run:

```bash
curl -X POST http://localhost:8000/api/v1/assignments/run \
  -H "Content-Type: application/json" \
  -d '{"run_type":"type-balance","triggered_by":"ops"}'
```

Fetch run status:

```bash
curl http://localhost:8000/api/v1/assignments/{run_id}
```

### 6) Verify services

- Backend health: `http://localhost:8000/api/v1/health`
- Backend docs: `http://localhost:8000/docs`
- Frontend: `http://localhost:5173`

## Testing

```bash
cd backend
pytest -q
```


## Local DB Reset (exact commands)

Use these commands to reset to a clean local state and rerun migrations/seeds:

```bash
docker compose down -v --remove-orphans
docker compose up -d db
# wait for postgres healthcheck to pass
docker compose up -d backend

docker compose exec backend alembic upgrade head
docker compose exec backend python -m scripts.seed_defaults
```

To verify required tables exist:

```bash
docker compose exec db psql -U postgres -d hotel_balancer -c "\dt"
```
