from datetime import date

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app.db.base import Base
from app.models.assignment_result import AssignmentResult
from app.models.manual_override import ManualOverride
from app.models.reservation import Reservation
from app.models.reservation_request import ReservationRequest
from app.models.room import Room
from app.services.assignment_engine import run_assignment_engine


engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base.metadata.create_all(bind=engine)


def _seed_base_data(db: Session) -> dict[str, int]:
    db.query(AssignmentResult).delete()
    db.query(ReservationRequest).delete()
    db.query(ManualOverride).delete()
    db.query(Reservation).delete()
    db.query(Room).delete()
    db.commit()

    rooms = [
        Room(room_number="101", room_type="KING", floor=1, is_active=True),
        Room(room_number="102", room_type="KING", floor=1, is_active=True),
        Room(room_number="CLUB201", room_type="CLUB_KING", floor=2, is_active=True),
        Room(room_number="NUA301", room_type="KING", floor=3, is_active=True),
    ]
    db.add_all(rooms)
    db.flush()

    reservations = [
        Reservation(external_id="R1", guest_name="Alice", arrival_date=date(2026, 4, 1), departure_date=date(2026, 4, 2), requested_room_type="KING", status="booked"),
        Reservation(external_id="R2", guest_name="Alice", arrival_date=date(2026, 4, 2), departure_date=date(2026, 4, 3), requested_room_type="KING", status="booked"),
        Reservation(external_id="R3", guest_name="Bob", arrival_date=date(2026, 4, 1), departure_date=date(2026, 4, 2), requested_room_type="KING", assigned_room_id=rooms[1].id, status="booked"),
    ]
    db.add_all(reservations)
    db.flush()

    db.add(ManualOverride(reservation_id=reservations[0].id, room_id=rooms[0].id, reason="VIP", applied_by="ops"))
    db.add(ReservationRequest(reservation_id=reservations[2].id, request_code="R4"))
    db.add(ReservationRequest(reservation_id=reservations[2].id, request_code="DIRECT_BOOKED_CLUB"))
    db.commit()

    return {
        "r1": reservations[0].id,
        "r2": reservations[1].id,
        "r3": reservations[2].id,
        "room101": rooms[0].id,
        "room102": rooms[1].id,
        "room_nua": rooms[3].id,
    }


def test_assignment_engine_run_type_balance_enforces_key_rules() -> None:
    with SessionLocal() as db:
        ids = _seed_base_data(db)
        run = run_assignment_engine(db=db, run_type="type-balance", triggered_by="test")
        results = list(db.scalars(select(AssignmentResult).where(AssignmentResult.assignment_run_id == run.id)))

        assert len(results) == 3
        r1 = next(result for result in results if result.reservation_id == ids["r1"])
        r2 = next(result for result in results if result.reservation_id == ids["r2"])
        r3 = next(result for result in results if result.reservation_id == ids["r3"])

        assert r1.room_id == ids["room101"]
        assert r2.room_id == r1.room_id
        assert r3.room_id == ids["room102"]
        assert all(result.room_id != ids["room_nua"] for result in results if result.room_id is not None)


def test_assignment_engine_exact_room_run_type() -> None:
    with SessionLocal() as db:
        _seed_base_data(db)
        run = run_assignment_engine(db=db, run_type="exact-room", triggered_by="test")
        assert run.run_type == "exact-room"
        assert run.run_status == "completed"
