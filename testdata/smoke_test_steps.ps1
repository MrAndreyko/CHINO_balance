# PowerShell smoke-test sequence for CHINO_balance
# Run from repo root after docker compose is up and migrations + seed are done.

# 1) Preview imports
curl.exe -X POST -F "file=@/mnt/data/chino_fake_dataset/rooms.csv" http://localhost:8000/api/v1/imports/room_master/preview
curl.exe -X POST -F "file=@/mnt/data/chino_fake_dataset/request_code_rules.csv" http://localhost:8000/api/v1/imports/request_code_rules/preview
curl.exe -X POST -F "file=@/mnt/data/chino_fake_dataset/reservations.csv" http://localhost:8000/api/v1/imports/reservations/preview
curl.exe -X POST -F "file=@/mnt/data/chino_fake_dataset/inventory_overrides.csv" http://localhost:8000/api/v1/imports/inventory_overrides/preview

# 2) Commit the preview jobs by replacing {job_id}
curl.exe -X POST http://localhost:8000/api/v1/imports/{job_id}/commit

# 3) Optional: apply compatibility rules and request codes
Get-Content /mnt/data/chino_fake_dataset/optional_test_enhancements.sql | docker compose exec -T db psql -U postgres -d hotel_room_balancer

# 4) Run assignment engine
curl.exe -X POST http://localhost:8000/api/v1/assignments/run -H "Content-Type: application/json" -d "{\"run_type\":\"type-balance\",\"triggered_by\":\"smoke-test\"}"
curl.exe -X POST http://localhost:8000/api/v1/assignments/run -H "Content-Type: application/json" -d "{\"run_type\":\"exact-room\",\"triggered_by\":\"smoke-test\"}"

# 5) Check assignment run metadata by replacing {run_id}
curl.exe http://localhost:8000/api/v1/assignments/{run_id}

# 6) Inspect actual assignment results inside Postgres
docker compose exec db psql -U postgres -d hotel_room_balancer -c "SELECT ar.assignment_run_id, r.external_id, rm.room_number, rm.room_type, ar.score, ar.reason_codes, ar.request_misses, ar.manual_review_flags FROM assignment_results ar LEFT JOIN reservations r ON r.id = ar.reservation_id LEFT JOIN rooms rm ON rm.id = ar.room_id ORDER BY ar.assignment_run_id, r.external_id;"
