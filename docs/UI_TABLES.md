> **Current release context — 04.10.2026:** Historical/date-specific findings in this document are preserved. Current release verification is **256 passed, 1 skipped** with `compileall` PASS. Known Promotions API shutdown risk is documented in `docs/API_RECONCILIATION.md` and `docs/RELEASE_AUDIT.md`.

# UI Tables — Current Contract

## Candidates

| Column | Meaning |
|---|---|
| Выбор | Selection checkbox. |
| SKU | Ozon SKU used to find the product card. |
| Название | Product name. |
| Цена | Current product price and source for Elastic Boosting calculation. |
| Ограничение для акций | Ozon `max_action_price`, informational only. It is not the application-side lower price bound. |
| Alert max action price failed | Ozon alert/error flag. |
| Alert max action price | Ozon alert value. |
| Price min elastic | Ozon `price_min_elastic` when returned. |
| Price max elastic | Ozon `price_max_elastic` when returned. |

## Participants

| Column | Meaning |
|---|---|
| Выбор | Selection checkbox. |
| SKU | Ozon SKU used to find the product card. |
| Название | Product name. |
| Цена | Product price before the current action discount. |
| Ограничение для акции | Ozon `max_action_price`. |
| Скидка | `(Цена - текущая action price) / Цена × 100%`. |
| Price min elastic | Ozon `price_min_elastic` when returned. |
| Price max elastic | Ozon `price_max_elastic` when returned. |

The participant table does not expose `Current boost`, `Min boost`, `Max boost`, or `Offer ID`. `Action price` remains represented by the current promotion price in the operation preview.

## Elastic Boosting editor

### Candidate ADD

For each candidate the editor calculates an individual discount interval from
`price_min_elastic` and `price_max_elastic`. The columns show `N% → price`,
for example `14.30% → 2314 ₽` and `29.15% → 1913 ₽`. A new candidate starts
at its minimum required discount. Manual editing is restricted to that
product's calculated interval.

### Participant UPDATE

The participant price editor uses the same per-product Ozon `price_min_elastic` /
`price_max_elastic` interval as Candidate ADD. There is no fixed `1%–18%`
application rule. The editor displays the calculated boundary percentages as
`N% → price`, and manual editing is restricted to the current product interval.

The UPDATE_PRICE service repeats this validation after Fresh Check and before
snapshot/mutation.

The UPDATE dialog also provides **Единый процент для всех выбранных товаров**. The user enters one percentage manually. The value is checked against every selected product. If any product requires a higher minimum discount, the global operation is rejected without changing the package; values above an individual maximum are likewise rejected.

Removed from these editors: `Авторасчёт`, manual value input, `Округление`, and `Safety Floor`.

## Dialog closing

Custom `Закрыть` buttons are not used. The native dialog **×** and **Esc** close the dialog.


## Auto-Add Ozon
The Actions section contains a third table, alongside Candidates and Participants. It uses the same `ozon_package_editor` component and therefore the same sorting, right-click header filtering, checkbox-only row selection, Shift-range selection, and text selection/copy behavior.

The table now exposes a calculated `Скидка` column. The value is derived locally from the Ozon-returned `price` and `action_price_to_auto_add` fields: `(price - action_price_to_auto_add) / price * 100`. This is an application-derived informational value, not a dedicated Ozon response field. Negative values are preserved when the Auto-Add action price is higher than the current price.

For selectable tables, clicking the first checkbox column header selects/deselects all visible rows. Shift+LMB and Shift+RMB both select a visible range from the current anchor.

A single local control allows the user to enter a threshold and hide all visible rows whose calculated discount is strictly greater than that threshold. This operation only changes the current table view; it does not call an Ozon mutation endpoint. Refreshing the Ozon data clears the local hidden-row state.

### Auto-Add mutation flow
The Auto-Add threshold action now prepares a real Ozon deletion plan. The button does not immediately mutate: it opens a Preview containing Product ID, SKU, name, price, Auto-Add action price and calculated discount, followed by explicit confirmation. The mutation is blocked if the current Ozon row differs from Preview or disappears before mutation.


## Loading modal

All long-running operations and checks use a centered modal loading overlay. Current stages include account connection verification, promotion/product reads, Auto-Add reads, Product ID → card enrichment, reconciliation, rollback preparation/execution, participant removal, ADD and Participant UPDATE. The modal shows the current step and blocks accidental interaction with the page while the operation is running.

The loading overlay is a presentation layer only. It does not replace Preview, Fresh Check, Snapshot, Confirmation or read-after-write verification.
