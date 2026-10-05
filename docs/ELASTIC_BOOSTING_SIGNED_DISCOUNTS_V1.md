# Elastic Boosting — Signed Discounts V1

## Purpose

This patch corrects Ozon Manager's interpretation of Elastic Boosting thresholds when Ozon returns a threshold price above the current product price.

The resulting percentage is a valid **negative discount** and must stay signed.

Example:

```text
Current price:       1000 ₽
price_min_elastic:   1050 ₽
price_max_elastic:    800 ₽

minimum discount = (1000 - 1050) / 1000 × 100 = -5%
maximum discount = (1000 - 800) / 1000 × 100 = 20%

valid interval: -5% … 20%
```

`-5%` is not an empty value and is not normalized to `0%`.

## Behaviour changed

- `elastic_discount_bounds()` now preserves signed percentages instead of clamping them to zero.
- `price_min_elastic > current price` is no longer rejected merely because it implies a negative minimum discount.
- Candidate ADD calculation accepts negative discounts when they remain inside Ozon's returned monetary interval.
- A negative discount is calculated as a price increase while retaining the same final monetary validation against `price_max_elastic ≤ requested price ≤ price_min_elastic`.
- Candidate and participant bulk threshold controls accept negative values.
- Participant global percentage input accepts negative values and still validates each product independently.
- Auto-Add threshold filtering accepts negative thresholds; Auto-Add already preserved negative calculated discount values.
- Candidate display and table filtering preserve negative percentages such as `-5.00%`.

## Safety boundaries retained

No Ozon endpoint, request schema, mutation transport, retry policy, Snapshot, Fresh Check, read-after-write verification, rollback transport, or identifier mapping was changed.

The ADD / UPDATE safety validation remains fail-closed and continues to validate the final requested price against the latest Ozon `price_min_elastic` / `price_max_elastic` interval before mutation.

## Verification

- Full suite: 265 tests collected; 264 passed; 1 existing Streamlit-environment smoke test skipped.
- Python `compileall`: PASS.
- Custom-table JavaScript syntax: PASS.
- Signed filter checks: PASS for `-5%`, `-1.83%`, `>= -5%`, `<= -2%`.
- Added regression tests for negative candidate minimum bounds, negative ADD calculations, global signed percentage, candidate display, and negative Auto-Add thresholds.
