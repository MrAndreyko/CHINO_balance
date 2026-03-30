from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from statistics import mean

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.assignment_result import AssignmentResult
from app.models.assignment_run import AssignmentRun
from app.models.compatibility_rule import CompatibilityRule
from app.models.inventory_override import InventoryOverride
from app.models.manual_override import ManualOverride
from app.models.reservation import Reservation
from app.models.reservation_request import ReservationRequest
from app.models.room import Room
from app.models.weights_config import WeightsConfig

STRONG_SOFT_CODES = {"A1", "C1"}
SOFT_CODES = {"B7", "H1", "N1"}
HARD_CODES = {"A5", "A9", "B4"}
BLOCKING_INVENTORY_STATUSES = {"hardblock", "out_of_order", "maintenance"}


@dataclass
class ReservationContext:
    reservation: Reservation
    request_codes: set[str] = field(default_factory=set)
    chain_id: str | None = None
    frozen_room_id: int | None = None
    manual_review_flags: list[str] = field(default_factory=list)


def _load_weights(db: Session) -> dict[str, float]:
    weights = {
        "strong_soft": 4.0,
        "soft": 2.0,
        "room_type_match": 8.0,
        "upgrade_path": 4.0,
        "balance_penalty": 1.0,
        "exact_room_boost": 12.0,
    }
    for row in db.scalars(select(WeightsConfig)):
        weights[row.key] = row.value
    return weights


def _build_request_map(db: Session) -> dict[int, set[str]]:
    request_map: dict[int, set[str]] = defaultdict(set)
    for req in db.scalars(select(ReservationRequest)):
        request_map[req.reservation_id].add(req.request_code)
    return request_map


def _build_compatibility_map(db: Session) -> dict[str, set[str]]:
    mapping: dict[str, set[str]] = defaultdict(set)
    for rule in db.scalars(select(CompatibilityRule).where(CompatibilityRule.is_compatible.is_(True))):
        mapping[rule.source_type].add(rule.target_type)
    return mapping


def _chain_reservations(reservations: list[Reservation]) -> dict[int, str]:
    chains: dict[int, str] = {}

    for reservation in reservations:
        if reservation.chain_id:
            chains[reservation.id] = reservation.chain_id

    by_external = {reservation.external_id: reservation for reservation in reservations}
    chain_index = 1
    for reservation in reservations:
        if reservation.id in chains or reservation.linked_reservation_id is None:
            continue
        chain_name = f"LINK-{chain_index}"
        chain_index += 1
        current = reservation
        while current and current.id not in chains:
            chains[current.id] = chain_name
            next_res = next((res for res in reservations if res.linked_reservation_id == current.id), None)
            current = next_res

    return chains


def _frozen_rooms(rooms: list[Room]) -> set[int]:
    return {room.id for room in rooms if room.is_hardblocked}


def _manual_overrides(db: Session) -> dict[int, int]:
    return {override.reservation_id: override.room_id for override in db.scalars(select(ManualOverride))}


def _inventory_blocked_rooms(db: Session) -> set[int]:
    blocked: set[int] = set()
    for override in db.scalars(select(InventoryOverride)):
        if override.status.lower() in BLOCKING_INVENTORY_STATUSES:
            blocked.add(override.room_id)
    return blocked


def _room_meets_hard_request_codes(room: Room, codes: set[str]) -> bool:
    if "A5" in codes and not room.is_accessible:
        return False
    if "A9" in codes and room.floor < 3:
        return False
    if "B4" in codes and not room.is_near_elevator:
        return False
    return True


def _room_type_compatible(requested_room_type: str, room_type: str, compatibility_map: dict[str, set[str]]) -> tuple[bool, bool]:
    if room_type == requested_room_type:
        return True, False
    if room_type in compatibility_map.get(requested_room_type, set()):
        return True, True
    return False, False


def _candidate_rooms(ctx: ReservationContext, rooms: list[Room], frozen: set[int], compatibility_map: dict[str, set[str]]) -> list[Room]:
    candidates: list[Room] = []
    for room in rooms:
        if not room.is_active or room.id in frozen:
            continue
        if ctx.reservation.requested_bed_type != "unknown" and room.bed_type != ctx.reservation.requested_bed_type:
            continue
        if not _room_meets_hard_request_codes(room, ctx.request_codes.intersection(HARD_CODES)):
            continue
        type_ok, _ = _room_type_compatible(ctx.reservation.requested_room_type, room.room_type, compatibility_map)
        if not type_ok:
            continue
        if ctx.reservation.club_access_entitled and not room.is_club_floor:
            continue
        candidates.append(room)
    return candidates


def _reservation_sort_key(ctx: ReservationContext, candidates_count: int) -> tuple[int, int, date]:
    entitlement_priority = 1 if ctx.reservation.club_access_entitled else 0
    return (candidates_count, -entitlement_priority, ctx.reservation.arrival_date)


def _score_room(
    ctx: ReservationContext,
    room: Room,
    run_type: str,
    current_counts: dict[str, int],
    target_mean: float,
    compatibility_map: dict[str, set[str]],
    weights: dict[str, float],
) -> tuple[float, list[str], list[str], list[str]]:
    score = 0.0
    reason_codes: list[str] = []
    misses: list[str] = []
    flags: list[str] = list(ctx.manual_review_flags)

    type_ok, is_upgrade = _room_type_compatible(ctx.reservation.requested_room_type, room.room_type, compatibility_map)
    if type_ok and not is_upgrade:
        score += weights["room_type_match"]
        reason_codes.append("ROOM_TYPE_MATCH")
    elif type_ok and is_upgrade:
        score += weights["upgrade_path"]
        reason_codes.append("UPGRADE_PATH_USED")

    if room.bed_type == ctx.reservation.requested_bed_type:
        reason_codes.append("BED_TYPE_GUARANTEED")
    else:
        misses.append("BED_TYPE")

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
        score -= abs(projected - target_mean) * weights["balance_penalty"]
    elif run_type == "exact-room" and ctx.reservation.assigned_room_id == room.id:
        score += weights["exact_room_boost"]
        reason_codes.append("EXACT_ROOM_PRESERVED")

    if ctx.reservation.club_access_entitled and not room.is_club_floor:
        misses.append("CLUB_ACCESS_ENTITLEMENT")
        flags.append("CLUB_ACCESS_BREACH")

    if not ctx.reservation.club_access_entitled and room.is_club_floor:
        reason_codes.append("CLUB_UPGRADE_NO_AUTO_ACCESS")

    return score, reason_codes, misses, flags


def run_assignment_engine(db: Session, run_type: str, triggered_by: str = "system") -> AssignmentRun:
    if run_type not in {"type-balance", "exact-room"}:
        raise ValueError("Unsupported run_type")

    weights = _load_weights(db)
    compatibility_map = _build_compatibility_map(db)
    rooms = list(db.scalars(select(Room)))
    reservations = list(db.scalars(select(Reservation).where(Reservation.status == "booked")))
    request_map = _build_request_map(db)
    chains = _chain_reservations(reservations)

    frozen = _frozen_rooms(rooms)
    frozen.update(_inventory_blocked_rooms(db))
    manual_map = _manual_overrides(db)

    contexts = [
        ReservationContext(
            reservation=reservation,
            request_codes=request_map.get(reservation.id, set()),
            chain_id=chains.get(reservation.id),
            frozen_room_id=manual_map.get(reservation.id),
            manual_review_flags=["NON_BALANCING_DEFAULT"] if "R4" in request_map.get(reservation.id, set()) else [],
        )
        for reservation in reservations
    ]

    run = AssignmentRun(run_type=run_type, run_status="running", triggered_by=triggered_by, notes="v1 assignment engine")
    db.add(run)
    db.flush()

    assigned_room_by_reservation: dict[int, int] = {}
    room_occupied: set[int] = set()
    current_counts: dict[str, int] = defaultdict(int)

    for ctx in contexts:
        if ctx.frozen_room_id and ctx.frozen_room_id not in frozen:
            assigned_room_by_reservation[ctx.reservation.id] = ctx.frozen_room_id
            room_occupied.add(ctx.frozen_room_id)
            room = next((r for r in rooms if r.id == ctx.frozen_room_id), None)
            if room:
                current_counts[room.room_type] += 1

    chain_groups: dict[str, list[ReservationContext]] = defaultdict(list)
    for ctx in contexts:
        if ctx.chain_id:
            chain_groups[ctx.chain_id].append(ctx)

    for chain_id, group in chain_groups.items():
        del chain_id
        preassigned = next((assigned_room_by_reservation.get(ctx.reservation.id) for ctx in group if ctx.reservation.id in assigned_room_by_reservation), None)
        if preassigned:
            selected = next((room for room in rooms if room.id == preassigned), None)
            for ctx in group:
                assigned_room_by_reservation[ctx.reservation.id] = preassigned
            if selected:
                current_counts[selected.room_type] += len(group)
            continue

        candidates = [room for room in _candidate_rooms(group[0], rooms, frozen, compatibility_map) if room.id not in room_occupied]
        if candidates:
            chosen = candidates[0]
            for ctx in group:
                assigned_room_by_reservation[ctx.reservation.id] = chosen.id
            room_occupied.add(chosen.id)
            current_counts[chosen.room_type] += len(group)

    pending = [ctx for ctx in contexts if ctx.reservation.id not in assigned_room_by_reservation]
    candidates_map = {
        ctx.reservation.id: [room for room in _candidate_rooms(ctx, rooms, frozen, compatibility_map) if room.id not in room_occupied]
        for ctx in pending
    }

    target_mean = mean([current_counts[room.room_type] for room in rooms]) if rooms else 0.0
    pending.sort(key=lambda ctx: _reservation_sort_key(ctx, len(candidates_map[ctx.reservation.id])))

    results: dict[int, AssignmentResult] = {}
    for ctx in pending:
        if "R4" in ctx.request_codes and ctx.reservation.assigned_room_id and ctx.reservation.assigned_room_id not in frozen:
            assigned_room = next((room for room in candidates_map[ctx.reservation.id] if room.id == ctx.reservation.assigned_room_id), None)
            if assigned_room is not None:
                assigned_room_by_reservation[ctx.reservation.id] = ctx.reservation.assigned_room_id
                room_occupied.add(ctx.reservation.assigned_room_id)
                current_counts[assigned_room.room_type] += 1
                continue

        candidates = [room for room in candidates_map[ctx.reservation.id] if room.id not in room_occupied]
        if not candidates:
            ctx.manual_review_flags.append("NO_FEASIBLE_ROOM")
            results[ctx.reservation.id] = AssignmentResult(
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

        scored = [
            (
                *_score_room(ctx, room, run_type, current_counts, target_mean, compatibility_map, weights),
                room,
            )
            for room in candidates
        ]
        scored.sort(key=lambda item: item[0], reverse=True)
        best_score, reasons, misses, flags, best_room = scored[0]

        assigned_room_by_reservation[ctx.reservation.id] = best_room.id
        room_occupied.add(best_room.id)
        current_counts[best_room.room_type] += 1

        results[ctx.reservation.id] = AssignmentResult(
            assignment_run_id=run.id,
            reservation_id=ctx.reservation.id,
            room_id=best_room.id,
            score=best_score,
            rationale=f"Assigned room {best_room.room_number} using weighted greedy selection",
            reason_codes=reasons,
            request_misses=misses,
            manual_review_flags=flags,
        )

    # swap / repair pass
    unassigned = [item for item in results.values() if item.room_id is None]
    assigned = [item for item in results.values() if item.room_id is not None]
    for missing in unassigned:
        missing_res = next(ctx.reservation for ctx in contexts if ctx.reservation.id == missing.reservation_id)
        for occupied in assigned:
            if occupied.room_id is None:
                continue
            occupied_res = next(ctx.reservation for ctx in contexts if ctx.reservation.id == occupied.reservation_id)
            room = next(r for r in rooms if r.id == occupied.room_id)
            if occupied_res.club_access_entitled and room.is_club_floor:
                continue
            type_ok, _ = _room_type_compatible(missing_res.requested_room_type, room.room_type, compatibility_map)
            if type_ok and room.bed_type == missing_res.requested_bed_type:
                missing.room_id = room.id
                missing.reason_codes.append("REPAIR_SWAP")
                missing.rationale = "Repair pass swapped room into feasible slot"
                occupied.room_id = None
                occupied.manual_review_flags.append("REASSIGNMENT_NEEDED")
                break

    db.query(AssignmentResult).filter(AssignmentResult.assignment_run_id == run.id).delete()
    for ctx in contexts:
        result = results.get(ctx.reservation.id)
        if result is None:
            result = AssignmentResult(
                assignment_run_id=run.id,
                reservation_id=ctx.reservation.id,
                room_id=assigned_room_by_reservation.get(ctx.reservation.id),
                score=0,
                rationale="Assigned via pre-assignment stages",
                reason_codes=["PREASSIGNED"],
                request_misses=[],
                manual_review_flags=ctx.manual_review_flags,
            )
        db.add(result)

    run.run_status = "completed"
    run.metadata_json = {
        "reservations": len(reservations),
        "assigned": len([1 for ctx in contexts if assigned_room_by_reservation.get(ctx.reservation.id) or results.get(ctx.reservation.id, None)]),
        "manual_review": len([1 for r in results.values() if r.room_id is None]),
    }
    db.commit()
    db.refresh(run)
    return run
