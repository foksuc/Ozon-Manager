# Current release architecture status — 2026-10-04

The architecture below is the actual current project structure. This documentation update does not change the architecture or application code. The adapter remains the boundary for Ozon transport, including the currently used legacy Promotions mutation endpoints whose shutdown is planned for 2026-10-13.

---

# Architecture

```text
Streamlit UI
    ↓
Application Services
    ↓
Elastic Boosting Domain
    ↓
Ozon Promotions Adapter
    ↓
Ozon Seller API

SQLite ← repositories/history/snapshots/errors
```

## Layers

### UI
Presentation and user interaction only. No HTTP calls.

### Application services
PromotionService, ParticipantService, PreviewService, FreshCheckService, SnapshotService, MutationService, VerificationService, HistoryService, SafeRollbackService.

### Domain
Promotion, ProductState, Operation, OperationItem, SnapshotItem, MutationResult, VerificationResult, explicit operation state machine.

### Infrastructure
HTTP transport, SQLite, logging, configuration.

## Safety invariants

1. No Preview → no mutation.
2. No Fresh Check → no mutation.
3. No Snapshot → no mutation.
4. No explicit Confirmation → no mutation.
5. Base `price` is never a mutation target.
6. Target Boost never becomes an action_price through an inferred formula.
7. HTTP 200 is not business success.
8. Unknown mutation result is reconciled before any retry.
9. Per-SKU verification is mandatory.
10. Rollback uses the snapshot's original `action_price`, never base price.


## Current UI/application interaction contract

The Streamlit layer owns presentation state only. Price calculations remain in the Price Engine and Ozon reads/mutations remain behind the adapter/service boundary.

Participant UPDATE follows:

```text
selected participants
  → per-product Ozon Elastic bounds
  → optional global percentage
  → per-product validation
  → Preview
  → Fresh Check
  → Snapshot
  → Confirmation
  → mutation
  → read-after-write
  → persistent operation result
```

The global percentage operation is atomic at the UI-plan level: if any selected product is below its required minimum discount or above its permitted maximum, no product in the package is updated in the plan.

### Loading overlay

Long-running read/check/mutation paths use the shared `_loading_overlay()` UI primitive. It renders a centered modal overlay and exposes progress messages for the current phase. The overlay is used for account connection checks, Ozon reads, card enrichment, reconciliation, rollback preparation/execution, participant removal, Auto-Add operations and ADD/UPDATE mutation workflows.
