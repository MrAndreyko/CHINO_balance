from datetime import date

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401
from app.db.base import Base
from app.models.assignment_result import AssignmentResult
from app.models.compatibility_rule import CompatibilityRule
from app.models.inventory_override import InventoryOverride
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
    db.query(CompatibilityRule).delete()
    db.query(InventoryOverride).delete()
    db.query(Reservation).delete()
    db.query(Room).delete()
    db.commit()

    rooms = [
        Room(room_number="101", room_type="KING_STD", bed_type="KING", floor=1, is_active=True, is_accessible=True, is_near_elevator=True),
        Room(room_number="102", room_type="KING_STD", bed_type="KING", floor=4, is_active=True, is_accessible=True, is_near_elevator=True),
        Room(room_number="201", room_type="KING_CLUB", bed_type="KING", floor=5, is_active=True, is_club_floor=True),
        Room(room_number="301", room_type="KING_STD", bed_type="KING", floor=3, is_active=True, is_hardblocked=True),
    ]
    db.add_all(rooms)
    db.flush()

    reservations = [
        Reservation(external_id="R1", guest_name="Alice", arrival_date=date(2026, 4, 1), departure_date=date(2026, 4, 2), requested_room_type="KING_STD", requested_bed_type="KING", chain_id="CHAIN-1", status="booked"),
        Reservation(external_id="R2", guest_name="Alice", arrival_date=date(2026, 4, 2), departure_date=date(2026, 4, 3), requested_room_type="KING_STD", requested_bed_type="KING", chain_id="CHAIN-1", status="booked"),
        Reservation(external_id="R3", guest_name="Bob", arrival_date=date(2026, 4, 1), departure_date=date(2026, 4, 2), requested_room_type="KING_STD", requested_bed_type="KING", club_access_entitled=True, assigned_room_id=rooms[1].id, status="booked"),
        Reservation(external_id="R4", guest_name="Cara", arrival_date=date(2026, 4, 1), departure_date=date(2026, 4, 2), requested_room_type="KING_STD", requested_bed_type="KING", status="booked"),
    ]
    db.add_all(reservations)
    db.flush()

    db.add(ManualOverride(reservation_id=reservations[0].id, room_id=rooms[0].id, reason="VIP", applied_by="ops"))
    db.add(ReservationRequest(reservation_id=reservations[2].id, request_code="R4"))
    db.add(ReservationRequest(reservation_id=reservations[3].id, request_code="A5"))

    db.add(CompatibilityRule(source_type="KING_STD", target_type="KING_CLUB", is_compatible=True, reason="upgrade"))
    db.add(InventoryOverride(room_id=rooms[3].id, override_date=date(2026, 4, 1), capacity_delta=0, status="hardblock", reason="OOS"))
    db.commit()

    return {
        "r1": reservations[0].id,
        "r2": reservations[1].id,
        "r3": reservations[2].id,
        "r4": reservations[3].id,
        "room101": rooms[0].id,
        "room102": rooms[1].id,
        "room_club": rooms[2].id,
        "room_blocked": rooms[3].id,
    }


def test_assignment_engine_preconditions_and_rules() -> None:
    with SessionLocal() as db:
        ids = _seed_base_data(db)
        run = run_assignment_engine(db=db, run_type="type-balance", triggered_by="test")
        results = list(db.scalars(select(AssignmentResult).where(AssignmentResult.assignment_run_id == run.id)))

        assert len(results) == 4
        r1 = next(result for result in results if result.reservation_id == ids["r1"])
        r2 = next(result for result in results if result.reservation_id == ids["r2"])
        r3 = next(result for result in results if result.reservation_id == ids["r3"])
        r4 = next(result for result in results if result.reservation_id == ids["r4"])

        # explicit chain_id preserves same room across B2B
        assert r1.room_id == ids["room101"]
        assert r2.room_id == r1.room_id

        # club entitlement from reservation field
        assert r3.room_id == ids["room_club"]

        # accessibility code A5 uses explicit room attribute, not notes parsing
        assert r4.room_id in {ids["room101"], ids["room102"], ids["room_club"]}
        assert all(result.room_id != ids["room_blocked"] for result in results if result.room_id is not None)


def test_assignment_engine_exact_room_run_type() -> None:
    with SessionLocal() as db:
        _seed_base_data(db)
        run = run_assignment_engine(db=db, run_type="exact-room", triggered_by="test")
        assert run.run_type == "exact-room"
        assert run.run_status == "completed"
