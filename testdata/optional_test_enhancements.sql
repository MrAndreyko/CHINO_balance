-- Optional helper SQL because the current API does NOT import compatibility_rules or reservation_requests yet.
-- Run inside Postgres after importing the CSV files.

-- Compatibility rules: allow TNK guests to use CLHF and RVK as upgrade paths.
INSERT INTO compatibility_rules (source_type, target_type, is_compatible, reason)
VALUES
  ('TNK', 'CLHF', true, 'Test upgrade path'),
  ('TNK', 'RVK', true, 'Test upgrade path'),
  ('TNK', 'STE', true, 'Test suite upgrade path')
ON CONFLICT (source_type, target_type) DO UPDATE
SET is_compatible = EXCLUDED.is_compatible,
    reason = EXCLUDED.reason;

-- Request codes for the fake reservations.
-- RES-1002 has a soft near-elevator preference.
INSERT INTO reservation_requests (reservation_id, request_code, request_value)
SELECT id, 'N1', NULL FROM reservations WHERE external_id = 'RES-1002'
ON CONFLICT (reservation_id, request_code) DO NOTHING;

-- RES-1003 requires accessibility.
INSERT INTO reservation_requests (reservation_id, request_code, request_value)
SELECT id, 'A5', NULL FROM reservations WHERE external_id = 'RES-1003'
ON CONFLICT (reservation_id, request_code) DO NOTHING;

-- RES-1004 prefers high floor.
INSERT INTO reservation_requests (reservation_id, request_code, request_value)
SELECT id, 'H1', NULL FROM reservations WHERE external_id = 'RES-1004'
ON CONFLICT (reservation_id, request_code) DO NOTHING;

-- RES-1005 prefers away from elevator.
INSERT INTO reservation_requests (reservation_id, request_code, request_value)
SELECT id, 'B7', NULL FROM reservations WHERE external_id = 'RES-1005'
ON CONFLICT (reservation_id, request_code) DO NOTHING;
