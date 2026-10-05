> **Current release context — 04.10.2026:** This file is a historical phase report. Its dated findings are preserved for traceability. For the current release status, use `docs/RELEASE_AUDIT.md`, `docs/API_RECONCILIATION.md` and `README.md`.

# Phase 4D — Mutation Safety QA

Date: 2026-10-01

## Scope

Forensic QA of the mutation safety pipeline using the Mock Ozon adapter. No authenticated Ozon mutation was executed.

## Verified sequence

`Preview → Fresh Check → Snapshot → Confirmation → Mutation → Read-after-write → History`

Rollback was tested as an independent mutation:

`Snapshot selection → Rollback Preview/Fresh Check → Snapshot → Confirmation → Mutation → Read-after-write → History`

## Results

- Preview without mutation: PASS
- Mutation without Preview: BLOCKED
- Mutation without Snapshot: BLOCKED
- Mutation without Confirmation: BLOCKED
- Pre-mutation Fresh Check: mandatory and PASS when state is unchanged
- Stale `action_price`: mutation blocked before update request
- Stale `current_boost`: mutation blocked before update request
- Inactive promotion: mutation blocked before update request
- Partial rejection: persisted per SKU and classified as PARTIAL after verification
- Read-after-write mismatch: classified as VERIFICATION_FAILED
- Unknown mutation result: operation becomes VERIFICATION_FAILED; blind retry is blocked
- Unknown result after mock state change: retry remains blocked
- Duplicate request fingerprint: blocked
- Rollback: uses source snapshot, creates a new snapshot, requires confirmation, and passes through the same mutation gates
- Rollback stale state: blocked before second mutation
- Snapshot linkage: persisted with the `snapshot_id` and `SNAPSHOTTED` status before confirmation

## Defect found and fixed

`SnapshotService.create()` previously persisted the operation before setting `snapshot_id` and `SNAPSHOTTED`. The snapshot itself could exist while the operation history still showed no snapshot linkage if the process stopped at that boundary.

The service now persists the final snapshot linkage/status after snapshot creation. Mutation remains impossible unless the in-memory operation has a snapshot and reaches `CONFIRMED`.

## Test result

`pytest -q` at the time of that historical phase: **72 passed**

`python -m compileall -q app tests`: **PASS**

## Release gate remaining

This QA proves the application safety logic with a deterministic mock adapter. It does **not** prove that an authenticated Ozon mutation succeeds against the live Seller API. A controlled live probe on an already eligible participant remains required before declaring production mutation release-ready.
