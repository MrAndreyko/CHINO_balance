import os
import subprocess
from pathlib import Path
from urllib.parse import urlparse

import psycopg
import pytest


REQUIRED_TABLES = {
    "request_code_rules",
    "weights_config",
    "reservation_requests",
    "compatibility_rules",
    "import_jobs",
    "import_job_errors",
}


@pytest.mark.integration
def test_fresh_postgres_migration_chain() -> None:
    database_url = os.getenv("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("TEST_DATABASE_URL is not set; skipping PostgreSQL migration integration test")

    parsed = urlparse(database_url)
    if parsed.scheme not in {"postgresql", "postgres"}:
        pytest.skip("TEST_DATABASE_URL must be a PostgreSQL URL")

    repo_backend = Path(__file__).resolve().parents[1]

    env = os.environ.copy()
    env.update(
        {
            "HRB_DB_HOST": parsed.hostname or "localhost",
            "HRB_DB_PORT": str(parsed.port or 5432),
            "HRB_DB_USER": parsed.username or "postgres",
            "HRB_DB_PASSWORD": parsed.password or "",
            "HRB_DB_NAME": parsed.path.lstrip("/"),
        }
    )

    subprocess.run(["alembic", "upgrade", "head"], cwd=repo_backend, env=env, check=True)

    with psycopg.connect(database_url) as conn, conn.cursor() as cur:
        cur.execute(
            """
            select table_name
            from information_schema.tables
            where table_schema = 'public'
            """
        )
        tables = {row[0] for row in cur.fetchall()}

    missing = REQUIRED_TABLES - tables
    assert not missing, f"Missing required tables after migration: {sorted(missing)}"
