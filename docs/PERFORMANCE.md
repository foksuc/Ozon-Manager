> **Current release context — 04.10.2026:** Historical/date-specific findings in this document are preserved. Current release verification is **256 passed, 1 skipped** with `compileall` PASS. Known Promotions API shutdown risk is documented in `docs/API_RECONCILIATION.md` and `docs/RELEASE_AUDIT.md`.

# Performance Fix — Phase 4D

## Problem

The Streamlit page was performing Ozon read operations during every Streamlit
rerun. Widget interaction therefore could repeat promotions, candidates,
participants and product-name network calls.

## Implemented behavior

- Read-only promotion/product data is cached in `st.session_state` through
  `ReadDataCache`.
- Normal widget reruns do not repeat Ozon reads for the current action.
- Promotion/action read data has a 60-second session TTL.
- Product names are cached by Product ID for the lifetime of the Streamlit
  session.
- Only previously unresolved Product IDs are sent to the product-name resolver.
- `🔄 Обновить данные` explicitly clears the session read cache and triggers a
  fresh read.
- The UI and mutation workflow remain separate from the read cache.
- No credentials are stored in the cache.

## Why `st.cache_data` is not used for Ozon reads

A generic `st.cache_data` wrapper would require credentials or an adapter to be
part of the cache key. That is undesirable for a credential-bearing local
application. The implementation therefore uses per-session state instead,
which gives the required rerun performance benefit without putting credentials
into a persistent/shared cache key.

## Expected request behavior

For one selected promotion:

1. First load: promotions + candidates + participants + unresolved product names.
2. Normal widget rerun: no Ozon read for the cached data.
3. New Product IDs: only those IDs are sent to product-name lookup.
4. After 60 seconds: the current action read data may refresh automatically.
5. Manual refresh: all read data and cached names are discarded and fetched again.

## Safety

This change is read-only. It does not alter mutation contracts, mutation batch
rules, snapshot behavior, rollback, or confirmation gates.

## Regression proof

The automated suite includes a cache-flow regression scenario with 900 unique
Product IDs. It verifies that:

- the first load performs one promotion read, one participant read and one
  candidate read;
- the first name resolution covers all 900 IDs;
- a normal cached rerun performs no additional promotion/participant/candidate
  reads and no duplicate name lookup;
- when three new Product IDs appear, only those three IDs are resolved.

This is a deterministic mock test, not a measurement of latency against live
Ozon. Live request counts and wall-clock latency remain an acceptance check
that requires the user's real Ozon environment.
