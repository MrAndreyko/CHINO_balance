Fake dataset for CHINO_balance smoke testing.

Files:
- rooms.csv
- request_code_rules.csv
- reservations.csv
- inventory_overrides.csv
- optional_test_enhancements.sql
- smoke_test_steps.ps1

What this dataset proves:
1. Import preview/commit works.
2. The DB accepts rooms, reservations, request-code rules, and inventory overrides.
3. The assignment engine can create a run and store assignment_results.

What it does NOT fully prove:
1. Real hotel balancing quality.
2. Real request-code import flow, because the current API still does not import reservation_requests.
3. Real upgrade-path behavior, unless you also run optional_test_enhancements.sql to insert compatibility_rules.
