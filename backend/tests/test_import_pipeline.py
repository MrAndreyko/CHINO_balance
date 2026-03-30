import io

from fastapi.testclient import TestClient
from openpyxl import Workbook
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app.db.base import Base
from app.db.session import get_db
from app.main import app


engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base.metadata.create_all(bind=engine)


def override_get_db():
    db: Session = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)


def test_room_master_preview_csv_validation_errors() -> None:
    content = "room_number,room_type,bed_type,floor\n101,DELUXE,KING,1\n102,,KING,abc\n"
    response = client.post(
        "/api/v1/imports/room_master/preview",
        files={"file": ("rooms.csv", content, "text/csv")},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["total_rows"] == 2
    assert payload["valid_rows"] == 1
    assert payload["invalid_rows"] == 1
    assert any(err["row_number"] == 2 and err["column_name"] == "floor" for err in payload["errors"])


def test_request_code_rules_preview_and_commit_csv() -> None:
    content = "code,description,default_weight\nLATE_CHECKOUT,Late checkout requested,1.4\n"
    preview = client.post(
        "/api/v1/imports/request_code_rules/preview",
        files={"file": ("request_codes.csv", content, "text/csv")},
    )
    assert preview.status_code == 200
    preview_payload = preview.json()
    assert preview_payload["invalid_rows"] == 0

    commit = client.post(f"/api/v1/imports/{preview_payload['id']}/commit")
    assert commit.status_code == 200
    assert commit.json()["applied_rows"] == 1

    status = client.get(f"/api/v1/imports/{preview_payload['id']}")
    assert status.status_code == 200
    assert status.json()["status"] == "committed"


def test_inventory_overrides_preview_xlsx_reports_unknown_room() -> None:
    workbook = Workbook()
    ws = workbook.active
    ws.append(["room_number", "override_date", "capacity_delta", "status", "reason"])
    ws.append(["999", "2026-04-01", -1, "maintenance", "Maintenance"])
    stream = io.BytesIO()
    workbook.save(stream)

    response = client.post(
        "/api/v1/imports/inventory_overrides/preview",
        files={
            "file": (
                "inventory.xlsx",
                stream.getvalue(),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["invalid_rows"] == 1
    assert any("Unknown room_number" in err["message"] for err in payload["errors"])


def test_reservations_preview_missing_column_reports_header_error() -> None:
    content = "external_id,guest_name,arrival_date,departure_date,requested_bed_type\nR1,Jane,2026-04-01,2026-04-02,KING\n"
    response = client.post(
        "/api/v1/imports/reservations/preview",
        files={"file": ("reservations.csv", content, "text/csv")},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["valid_rows"] == 0
    assert any(err["row_number"] == 0 and err["column_name"] == "requested_room_type" for err in payload["errors"])
