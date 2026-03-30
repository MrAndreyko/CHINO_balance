from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from statistics import mean

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.assignment_result import AssignmentResult
from app.models.assignment_run import AssignmentRun
from app.models.inventory_override import InventoryOverride
from app.models.manual_override import ManualOverride
from app.models.reservation import Reservation
from app.models.reservation_request import ReservationRequest
from app.models.room import Room
from app.models.weights_config import WeightsConfig

STRONG_SOFT_CODES = {"A1", "C1"}
SOFT_CODES = {"B7", "H1", "N1"}
HARD_CODES = {"A5", "A9", "B4"}


@dataclass
class ReservationContext:
    reservation: Reservation
    request_codes: set[str] = field(default_factory=set)
    chain_id: str | None = None
    frozen_room_id: int | None = None
    manual_review_flags: list[str] = field(default_factory=list)


def _load_weights(db: Session) -> dict[str, float]:
    weights = {"strong_soft": 4.0, "soft": 2.0, "room_type_match": 8.0, "balance_penalty": 1.0, "exact_room_boost": 12.0}
    rows = list(db.scalars(select(WeightsConfig)))
    for row in rows:
        weights[row.key] = row.value
    return weights


def _build_request_map(db: Session) -> dict[int, set[str]]:
    request_map: dict[int, set[str]] = defaultdict(set)
    for req in db.scalars(select(ReservationRequest)):
        request_map[req.reservation_id].add(req.request_code)
    return request_map


def _chain_reservations(reservations: list[Reservation]) -> dict[int, str]:
    chains: dict[int, str] = {}
    grouped: dict[str, list[Reservation]] = defaultdict(list)
    for reservation in reservations:
        grouped[reservation.guest_name].append(reservation)

    chain_index = 1
    for _, guest_reservations in grouped.items():
        guest_reservations.sort(key=lambda res: res.arrival_date)
        current_chain = [guest_reservations[0]] if guest_reservations else []
        for reservation in guest_reservations[1:]:
            previous = current_chain[-1]
            contiguous = previous.departure_date == reservation.arrival_date
            if contiguous:
                current_chain.append(reservation)
            else:
                if len(current_chain) > 1:
                    chain_id = f"B2B-{chain_index}"
                    for item in current_chain:
                        chains[item.id] = chain_id
                    chain_index += 1
                current_chain = [reservation]
        if len(current_chain) > 1:
            chain_id = f"B2B-{chain_index}"
            for item in current_chain:
                chains[item.id] = chain_id
            chain_index += 1
    return chains


def _frozen_rooms(rooms: list[Room]) -> set[int]:
    frozen: set[int] = set()
    for room in rooms:
        marker = room.room_number.upper()
        if marker.startswith("NUA") or marker.startswith("GXP"):
            frozen.add(room.id)
    return frozen


def _manual_overrides(db: Session) -> dict[int, int]:
    overrides: dict[int, int] = {}
    for override in db.scalars(select(ManualOverride)):
        overrides[override.reservation_id] = override.room_id
    return overrides


def _inventory_blocked_rooms(db: Session) -> set[int]:
    blocked: set[int] = set()
    for inv in db.scalars(select(InventoryOverride).where(InventoryOverride.capacity_delta < 0)):
        blocked.add(inv.room_id)
    return blocked


def _candidate_rooms(ctx: ReservationContext, rooms: list[Room], frozen: set[int]) -> list[Room]:
    candidates: list[Room] = []
    for room in rooms:
        if not room.is_active or room.id in frozen:
            continue
        if room.room_type != ctx.reservation.requested_room_type:
            continue
        hard_codes = HARD_CODES.intersection(ctx.request_codes)
        if hard_codes:
            notes = (room.notes or "").upper()
            if not any(code in notes or code in room.room_type.upper() for code in hard_codes):
                continue
        candidates.append(room)
    return candidates


def _reservation_sort_key(ctx: ReservationContext, candidates_count: int) -> tuple[int, int, date]:
    high_priority = 1 if "DIRECT_BOOKED_CLUB" in ctx.request_codes else 0
    return (candidates_count, -high_priority, ctx.reservation.arrival_date)


def _score_room(
    ctx: ReservationContext,
    room: Room,
    run_type: str,
    current_counts: dict[str, int],
    target_mean: float,
    weights: dict[str, float],
) -> tuple[float, list[str], list[str], list[str]]:
    score = 0.0
    reason_codes: list[str] = []
    misses: list[str] = []
    flags: list[str] = list(ctx.manual_review_flags)

    if room.room_type == ctx.reservation.requested_room_type:
        score += weights["room_type_match"]
        reason_codes.append("BED_TYPE_GUARANTEED")

    for code in STRONG_SOFT_CODES:
        if code in ctx.request_codes:
            score += weights["strong_soft"]
            reason_codes.append(f"{code}_STRONG_MATCH")

    for code in SOFT_CODES:
        if code in ctx.request_codes:
            score += weights["soft"]
            reason_codes.append(f"{code}_SOFT_MATCH")

    if run_type == "type-balance":
        projected = current_counts[room.room_type] + 1
        imbalance = abs(projected - target_mean)
        score -= imbalance * weights["balance_penalty"]
    elif run_type == "exact-room" and ctx.reservation.assigned_room_id == room.id:
        score += weights["exact_room_boost"]
        reason_codes.append("EXACT_ROOM_PRESERVED")

    if "DIRECT_BOOKED_CLUB" in ctx.request_codes and "CLUB" not in room.room_type.upper():
        flags.append("DIRECT_BOOKED_CLUB_ENTITLEMENT_RISK")
        misses.append("DIRECT_BOOKED_CLUB")

    if "UPGRADED" in ctx.request_codes and "CLUB" in room.room_type.upper() and "DIRECT_BOOKED_CLUB" not in ctx.request_codes:
        reason_codes.append("CLUB_UPGRADE_NO_AUTO_ACCESS")

    return score, reason_codes, misses, flags


def run_assignment_engine(db: Session, run_type: str, triggered_by: str = "system") -> AssignmentRun:
    if run_type not in {"type-balance", "exact-room"}:
        raise ValueError("Unsupported run_type")

    weights = _load_weights(db)
    rooms = list(db.scalars(select(Room)))
    reservations = list(db.scalars(select(Reservation).where(Reservation.status == "booked")))
    request_map = _build_request_map(db)
    chains = _chain_reservations(reservations)

    frozen = _frozen_rooms(rooms)
    frozen.update(_inventory_blocked_rooms(db))
    manual_map = _manual_overrides(db)

    contexts: list[ReservationContext] = []
    for reservation in reservations:
        ctx = ReservationContext(
            reservation=reservation,
            request_codes=request_map.get(reservation.id, set()),
            chain_id=chains.get(reservation.id),
            frozen_room_id=manual_map.get(reservation.id),
        )
        if "R4" in ctx.request_codes:
            ctx.manual_review_flags.append("NON_BALANCING_DEFAULT")
        contexts.append(ctx)

    run = AssignmentRun(run_type=run_type, run_status="running", triggered_by=triggered_by, notes="v1 assignment engine")
    db.add(run)
    db.flush()

    assigned_room_by_reservation: dict[int, int] = {}
    room_occupied: set[int] = set()
    current_counts: dict[str, int] = defaultdict(int)

    # 3. freeze hardblocks/manual overrides
    for ctx in contexts:
        if ctx.frozen_room_id is not None and ctx.frozen_room_id not in frozen:
            assigned_room_by_reservation[ctx.reservation.id] = ctx.frozen_room_id
            room_occupied.add(ctx.frozen_room_id)
            room = next((room for room in rooms if room.id == ctx.frozen_room_id), None)
            if room:
                current_counts[room.room_type] += 1

    # 2. B2B chains same room before optimization
    chain_to_res_ids: dict[str, list[int]] = defaultdict(list)
    for ctx in contexts:
        if ctx.chain_id:
            chain_to_res_ids[ctx.chain_id].append(ctx.reservation.id)

    for _, reservation_ids in chain_to_res_ids.items():
        chain_contexts = [ctx for ctx in contexts if ctx.reservation.id in reservation_ids]
        preassigned_room_id = next((assigned_room_by_reservation.get(ctx.reservation.id) for ctx in chain_contexts if assigned_room_by_reservation.get(ctx.reservation.id) is not None), None)

        if preassigned_room_id is not None:
            selected = next((room for room in rooms if room.id == preassigned_room_id), None)
            for ctx in chain_contexts:
                assigned_room_by_reservation[ctx.reservation.id] = preassigned_room_id
            if selected:
                current_counts[selected.room_type] += len(chain_contexts)
            continue

        unassigned = [ctx for ctx in chain_contexts if ctx.reservation.id not in assigned_room_by_reservation]
        if not unassigned:
            continue
        anchor = unassigned[0]
        candidates = [room for room in _candidate_rooms(anchor, rooms, frozen) if room.id not in room_occupied]
        if candidates:
            selected = candidates[0]
            for ctx in unassigned:
                assigned_room_by_reservation[ctx.reservation.id] = selected.id
            room_occupied.add(selected.id)
            current_counts[selected.room_type] += len(unassigned)

    # 4/5/6 generate candidates, prioritize, greedy weighted assign
    pending_contexts = [ctx for ctx in contexts if ctx.reservation.id not in assigned_room_by_reservation]
    reservation_candidates: dict[int, list[Room]] = {
        ctx.reservation.id: [room for room in _candidate_rooms(ctx, rooms, frozen) if room.id not in room_occupied] for ctx in pending_contexts
    }

    target_mean = mean([current_counts[room.room_type] for room in rooms]) if rooms else 0.0
    pending_contexts.sort(key=lambda ctx: _reservation_sort_key(ctx, len(reservation_candidates[ctx.reservation.id])))

    result_rows: dict[int, AssignmentResult] = {}

    for ctx in pending_contexts:
        if "R4" in ctx.request_codes and ctx.reservation.assigned_room_id and ctx.reservation.assigned_room_id not in frozen:
            assigned_room_by_reservation[ctx.reservation.id] = ctx.reservation.assigned_room_id
            room_occupied.add(ctx.reservation.assigned_room_id)
            room = next((room for room in rooms if room.id == ctx.reservation.assigned_room_id), None)
            if room:
                current_counts[room.room_type] += 1
            continue

        candidates = [room for room in reservation_candidates[ctx.reservation.id] if room.id not in room_occupied]
        if not candidates:
            ctx.manual_review_flags.append("NO_FEASIBLE_ROOM")
            result_rows[ctx.reservation.id] = AssignmentResult(
                assignment_run_id=run.id,
                reservation_id=ctx.reservation.id,
                room_id=None,
                score=0,
                rationale="No feasible candidate room found",
                reason_codes=["MANUAL_REVIEW_REQUIRED"],
                request_misses=sorted(ctx.request_codes),
                manual_review_flags=ctx.manual_review_flags,
            )
            continue

        scored = []
        for room in candidates:
            score, reasons, misses, flags = _score_room(ctx, room, run_type, current_counts, target_mean, weights)
            scored.append((score, room, reasons, misses, flags))
        scored.sort(key=lambda item: item[0], reverse=True)
        best_score, best_room, reasons, misses, flags = scored[0]

        assigned_room_by_reservation[ctx.reservation.id] = best_room.id
        room_occupied.add(best_room.id)
        current_counts[best_room.room_type] += 1
        result_rows[ctx.reservation.id] = AssignmentResult(
            assignment_run_id=run.id,
            reservation_id=ctx.reservation.id,
            room_id=best_room.id,
            score=best_score,
            rationale=f"Assigned room {best_room.room_number} using weighted greedy selection",
            reason_codes=reasons,
            request_misses=misses,
            manual_review_flags=flags,
        )

    # 7. simple repair pass
    unassigned_results = [result for result in result_rows.values() if result.room_id is None]
    assigned_results = [result for result in result_rows.values() if result.room_id is not None]
    for missing in unassigned_results:
        for assigned in assigned_results:
            if assigned.room_id is None:
                continue
            missing_res = next(ctx.reservation for ctx in contexts if ctx.reservation.id == missing.reservation_id)
            assigned_res = next(ctx.reservation for ctx in contexts if ctx.reservation.id == assigned.reservation_id)
            swapped_room = next(room for room in rooms if room.id == assigned.room_id)
            if swapped_room.room_type == missing_res.requested_room_type and swapped_room.room_type != assigned_res.requested_room_type:
                missing.room_id = assigned.room_id
                missing.score = assigned.score - 0.1
                missing.rationale = "Repair pass: room swap to satisfy unassigned reservation"
                missing.reason_codes.append("REPAIR_SWAP")
                assigned.room_id = None
                assigned.manual_review_flags.append("REASSIGNMENT_NEEDED")
                assigned.request_misses.append("LOST_ROOM_IN_REPAIR")
                break

    db.query(AssignmentResult).filter(AssignmentResult.assignment_run_id == run.id).delete()
    for ctx in contexts:
        result = result_rows.get(ctx.reservation.id)
        if result is None:
            room_id = assigned_room_by_reservation.get(ctx.reservation.id)
            result = AssignmentResult(
                assignment_run_id=run.id,
                reservation_id=ctx.reservation.id,
                room_id=room_id,
                score=0,
                rationale="Assigned via chain/freeze pass",
                reason_codes=["PREASSIGNED"],
                request_misses=[],
                manual_review_flags=ctx.manual_review_flags,
            )
        db.add(result)

    run.run_status = "completed"
    run.metadata_json = {
        "reservations": len(reservations),
        "assigned": sum(1 for result in result_rows.values() if result.room_id is not None) + (len(reservations) - len(result_rows)),
        "manual_review": sum(1 for result in result_rows.values() if result.room_id is None),
    }
    db.commit()
    db.refresh(run)
    return run
