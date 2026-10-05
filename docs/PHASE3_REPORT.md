# Phase 3 Development Report

## Implemented

- repository structure;
- configuration and credentials boundary;
- Ozon Promotions adapter;
- domain models and authoritative operation state machine;
- SQLite repositories;
- Promotion / Participant / Preview / Fresh Check / Snapshot / Mutation / Verification / History / Rollback services;
- real mutation batching at 100 operation items per batch;
- per-SKU warning persistence and verification;
- Streamlit UI;
- mock adapter;
- unit, integration, contract, bulk, rollback-isolation and security tests.

## API contract

**API CONTRACT STATUS: RESOLVED**

The implementation follows the approved `API_SPEC_v1.6` contract:

- `GET /v1/actions`
- `POST /v1/actions/candidates`
- `POST /v1/actions/products`
- `POST /v1/actions/products/update`
- `POST /v2/actions/products`

`POST /v2/actions` is not used because it is not part of the approved contract. No undocumented endpoint has been introduced.

## Safety contract

- Mutation target is `action_price` only.
- Target Boost mutation remains blocked.
- Base-price mutation remains blocked.
- Blind retry remains prohibited.
- Unknown mutation outcomes are reconciled by read-after-write / verification rather than retried blindly.
- Rollback resolves the exact promotion from the snapshot's `action_id` and does not depend on the currently selected UI promotion.
- Mutation batches are limited by the application to 100 SKU per request; this is an application batching rule, **not** an asserted global Ozon API limit.

## Phase 3.1 status

All Phase 3.1 hardening requirements are covered by regression/integration tests and compile checks. Final release readiness is determined by the Phase 3.1 execution report.

## 2026-10-01 contract supersession

The earlier Phase 3 endpoint matrix is historical. The final 2026-10-01 reconciliation supersedes its read paths with `/v2/actions/candidates` and `/v2/actions/products` and supersedes the old `/v1/actions/products/update` mutation assumption. The live-verified action-price mutation path is `/v1/actions/products/activate`. See `docs/API_RECONCILIATION.md`, `docs/API_SPEC.md`, and `docs/PHASE_D3_REPORT.md`.
