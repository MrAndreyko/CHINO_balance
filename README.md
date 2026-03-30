# Hotel Room Balancing Service (v1 Bootstrap)

This repository contains a production-structured starter for a self-hosted hotel room-balancing platform.

## Stack

- **Backend**: Python, FastAPI, SQLAlchemy, Alembic
- **Database**: PostgreSQL
- **Frontend**: React (Vite scaffold)
- **Orchestration**: Docker Compose

> Scope of this bootstrap: structure, database setup, models, migrations, seed data, and local run flow.
> Not included yet: optimizer logic, PMS integrations, machine learning.

## Project Structure

```text
.
├── backend/
│   ├── app/
│   │   ├── api/v1/endpoints/health.py
│   │   ├── api/v1/router.py
│   │   ├── core/config.py
│   │   ├── db/
│   │   │   ├── base.py
│   │   │   └── session.py
│   │   ├── models/
│   │   │   ├── assignment_result.py
│   │   │   ├── assignment_run.py
│   │   │   ├── compatibility_rule.py
│   │   │   ├── inventory_override.py
│   │   │   ├── manual_override.py
│   │   │   ├── request_code_rule.py
│   │   │   ├── reservation.py
│   │   │   ├── reservation_request.py
│   │   │   ├── room.py
│   │   │   └── weights_config.py
│   │   └── main.py
│   ├── alembic/
│   │   ├── versions/0001_initial_schema.py
│   │   ├── env.py
│   │   └── script.py.mako
│   ├── scripts/seed_defaults.py
│   ├── alembic.ini
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── src/main.tsx
│   ├── package.json
│   └── vite.config.ts
├── docker-compose.yml
└── .env.example
```

## Database Entities in v1

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

### 5) Verify services

- Backend health: `http://localhost:8000/api/v1/health`
- Backend docs: `http://localhost:8000/docs`
- Frontend: `http://localhost:5173`

## Development Notes

- SQLAlchemy metadata naming conventions are configured for predictable constraints.
- Alembic is wired to application settings and includes an initial migration file.
- Seed script is idempotent (safe to run multiple times).

## Next Suggested Milestones

1. Introduce Pydantic schemas and CRUD services.
2. Add unit/integration tests with pytest + testcontainers.
3. Implement assignment orchestration API surface (without optimizer internals yet).
4. Add auth and audit logging.
