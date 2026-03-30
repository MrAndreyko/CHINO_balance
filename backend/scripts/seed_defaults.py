from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.request_code_rule import RequestCodeRule
from app.models.weights_config import WeightsConfig

DEFAULT_REQUEST_CODES = [
    {"code": "HIGH_FLOOR", "description": "Guest requests a higher floor", "default_weight": 1.2},
    {"code": "LOW_FLOOR", "description": "Guest requests a lower floor", "default_weight": 1.0},
    {"code": "QUIET_ZONE", "description": "Guest requests a quiet area", "default_weight": 1.5},
    {"code": "NEAR_ELEVATOR", "description": "Guest wants proximity to elevator", "default_weight": 0.7},
]

DEFAULT_WEIGHTS = [
    {"key": "request_match", "value": 2.0, "description": "Weight for matching explicit request codes"},
    {"key": "room_type_match", "value": 1.5, "description": "Weight for requested room type fit"},
    {"key": "stay_contiguity", "value": 1.0, "description": "Weight for avoiding room changes"},
    {"key": "manual_override_penalty", "value": -1.0, "description": "Penalty when manual overrides are required"},
]


def seed_request_code_rules() -> int:
    created = 0
    with SessionLocal() as session:
        for row in DEFAULT_REQUEST_CODES:
            exists = session.scalar(select(RequestCodeRule).where(RequestCodeRule.code == row["code"]))
            if exists is None:
                session.add(RequestCodeRule(**row))
                created += 1
        session.commit()
    return created


def seed_weights_config() -> int:
    created = 0
    with SessionLocal() as session:
        for row in DEFAULT_WEIGHTS:
            exists = session.scalar(select(WeightsConfig).where(WeightsConfig.key == row["key"]))
            if exists is None:
                session.add(WeightsConfig(**row))
                created += 1
        session.commit()
    return created


def main() -> None:
    created_request_codes = seed_request_code_rules()
    created_weights = seed_weights_config()
    print(f"Seed complete. request_code_rules={created_request_codes}, weights_config={created_weights}")


if __name__ == "__main__":
    main()
