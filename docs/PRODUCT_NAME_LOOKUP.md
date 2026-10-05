> **Current release context — 04.10.2026:** Historical/date-specific findings in this document are preserved. Current release verification is **256 passed, 1 skipped** with `compileall` PASS. Known Promotions API shutdown risk is documented in `docs/API_RECONCILIATION.md` and `docs/RELEASE_AUDIT.md`.

# Product Name Lookup

## Purpose

The UI now enriches candidate and participant rows with the Ozon product-card name using the read-only OzonAPI SDK method:

`/v3/product/info/list`

SDK method:

`SellerAPI.product_info_list(ProductInfoListRequest(product_id=[...]))`

## Flow

```text
Candidates + Participants
        |
        v
unique Product IDs
        |
        v
OzonAPI product_info_list
        |
        v
Product ID -> Name
        |
        +--> candidate table
        +--> participant table
```

## Safety boundary

This lookup is read-only. It does not alter Preview, Fresh Check, Snapshot, mutation, verification, rollback, or history behavior.

If Ozon returns no name for a Product ID, the UI displays `UNKNOWN`.

If the name lookup itself fails, the product tables remain available and the UI reports the lookup failure.

## Batch status

`OZON_PRODUCT_INFO_BATCH_SIZE=1000` is an **application-level batching setting**. It is not asserted as an Ozon API limit. The adapter splits product-info reads according to this local setting; the project does not infer an undocumented Ozon maximum from it.


## SKU для поиска карточки

UI теперь получает не только название, но и `sku` из product-info ответа Ozon для каждого `product_id`.
В таблицах колонка, ранее отображавшая `Product ID`, отображается как `SKU`. Внутри приложения исходный Ozon Product ID сохраняется отдельно и используется для mutation; пользователь видит SKU, чтобы находить карточку товара на Ozon.

Forensic-проверка конкретного товара также подтвердила связку `product_id=1494258615` → `sku=1940085241` через `/v3/product/info/list`.
