from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

import os

import requests

from app.adapters.ozon_sdk import OzonSDKPromotionsReader

from app.domain.models import MutationResult, ProductState, Promotion
from app.config import Settings


class OzonAPIError(RuntimeError):
    def __init__(self, message: str, *, status_code: int | None = None, category: str = "API_ERROR"):
        super().__init__(message)
        self.status_code = status_code
        self.category = category


@dataclass(frozen=True)
class OzonCredentials:
    client_id: str
    api_key: str


class OzonPromotionsAdapter:
    """Transport-only adapter for the audited Promotions contracts.

    Reconciled Promos contract (2026-09-28 OpenAPI review):
      GET  /v1/actions
      POST /v2/actions/candidates
      POST /v2/actions/products
      POST /v1/actions/products/activate
      POST /v1/actions/products/deactivate

    REMOVE note (live forensic verification, 2026-10-04): for Elastic Boosting
    action 1977747, this deprecated v1 endpoint removed product 6238154899
    and returned it in result.product_ids; the participant disappeared on
    read-after-write. The current /v2/actions/products/deactivate documentation
    describes Promocodes and does not replace this observed Elastic transport.
    The endpoint is scheduled for Ozon shutdown on 2026-10-13, so this is an
    explicit, time-bounded transport decision rather than a generic future API
    guarantee.

    The legacy candidate/participant read endpoints are not used. The v2 read
    responses are top-level (no ``result`` wrapper). Mutation uses a money
    object for action_price and returns per-product outcome categories.
    """

    def __init__(self, credentials: OzonCredentials, base_url: str = "https://api-seller.ozon.ru", timeout: float = 20.0, session: requests.Session | None = None, use_sdk: bool | None = None, product_info_batch_size: int | None = None):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        product_info_batch_size = Settings().product_info_batch_size if product_info_batch_size is None else product_info_batch_size
        if product_info_batch_size < 1:
            raise ValueError("product_info_batch_size must be >= 1")
        self.product_info_batch_size = product_info_batch_size
        self.session = session or requests.Session()
        self.use_sdk = (os.getenv("OZON_USE_SDK", "1") == "1") if use_sdk is None else use_sdk
        self.sdk_promotions = OzonSDKPromotionsReader(credentials.client_id, credentials.api_key) if self.use_sdk else None
        self.session.headers.update({
            "Client-Id": credentials.client_id,
            "Api-Key": credentials.api_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
        })

    def _request(self, method: str, path: str, payload: dict[str, Any] | None = None, *, return_status: bool = False):
        try:
            response = self.session.request(method, self.base_url + path, json=payload, timeout=self.timeout)
        except requests.Timeout as exc:
            raise OzonAPIError("Ozon request timed out", category="UNKNOWN_RESULT") from exc
        except requests.RequestException as exc:
            raise OzonAPIError("Ozon network request failed; mutation outcome may be unknown", category="UNKNOWN_RESULT") from exc

        if response.status_code in (401, 403):
            raise OzonAPIError("Ozon authentication/authorization failed", status_code=response.status_code, category="AUTH_ERROR")
        if response.status_code == 429:
            raise OzonAPIError("Ozon rate limit exceeded", status_code=429, category="RATE_LIMIT")
        if response.status_code >= 400:
            detail = ""
            try:
                body = response.json()
                detail = str(body.get("message") or body.get("error") or "")
            except ValueError:
                pass
            raise OzonAPIError(f"Ozon API error {response.status_code}: {detail}".strip(), status_code=response.status_code, category="API_ERROR")
        try:
            data = response.json() if response.content else {}
            return (data, response.status_code) if return_status else data
        except ValueError as exc:
            raise OzonAPIError("Ozon returned malformed JSON", status_code=response.status_code, category="API_ERROR") from exc

    @staticmethod
    def _json_number(value: Any) -> int | float | Any:
        """Convert domain Decimal to a JSON number at the HTTP boundary.

        Price calculations remain Decimal everywhere in the domain/services.
        Ozon's activate contract declares action_price as a JSON double, while
        requests/json cannot serialize Decimal directly.
        """
        if isinstance(value, Decimal):
            if value == value.to_integral_value():
                return int(value)
            return float(value)
        return value

    @staticmethod
    def _money(value: Any) -> Decimal | None:
        if value is None:
            return None
        if isinstance(value, dict):
            value = value.get("amount")
        if value is None:
            return None
        return Decimal(str(value))

    @staticmethod
    def _product(action_id: str, raw: dict[str, Any]) -> ProductState:
        product_id = raw.get("product_id")
        if product_id is None:
            product_id = raw.get("id")
        return ProductState(
            action_id=str(action_id),
            product_id=str(product_id),
            offer_id=str(raw["offer_id"]) if raw.get("offer_id") is not None else None,
            name=raw.get("name"),
            price=OzonPromotionsAdapter._money(raw.get("price")),
            action_price=OzonPromotionsAdapter._money(raw.get("action_price")) or Decimal("0"),
            current_boost=OzonPromotionsAdapter._money(raw.get("current_boost")),
            min_boost=OzonPromotionsAdapter._money(raw.get("min_boost")),
            max_boost=OzonPromotionsAdapter._money(raw.get("max_boost")),
            price_min_elastic=OzonPromotionsAdapter._money(raw.get("price_min_elastic")),
            price_max_elastic=OzonPromotionsAdapter._money(raw.get("price_max_elastic")),
            membership=raw.get("membership") or raw.get("status"),
            availability=raw.get("availability"),
            currency=(raw.get("action_price") or {}).get("currency", "RUB") if isinstance(raw.get("action_price"), dict) else "RUB",
            max_action_price=OzonPromotionsAdapter._money(raw.get("max_action_price")),
        )


    def _list_product_identifiers(self, *, limit: int = 1000) -> list[dict[str, Any]]:
        """Read the seller catalog and collect identifiers accepted by the FBS stock-by-warehouse API.

        `/v2/product/info/stocks-by-warehouse/fbs` requires `offer_id` or `sku`;
        it is not a catalogue/list endpoint. Catalog pagination is therefore
        performed through `/v3/product/list`, whose current contract supports
        `last_id` + `limit`.
        """
        if limit < 1:
            raise ValueError("product list limit must be >= 1")
        products: list[dict[str, Any]] = []
        last_id = ""
        while True:
            payload: dict[str, Any] = {"limit": int(limit), "filter": {"visibility": "ALL"}}
            if last_id:
                payload["last_id"] = last_id
            data = self._request("POST", "/v3/product/list", payload)
            result = data.get("result") if isinstance(data.get("result"), dict) else data
            page = result.get("items") or result.get("products") or data.get("items") or data.get("products") or []
            if not isinstance(page, list):
                page = []
            products.extend(item for item in page if isinstance(item, dict))
            next_last_id = result.get("last_id") or data.get("last_id")
            if not page or not next_last_id or str(next_last_id) == str(last_id):
                break
            last_id = str(next_last_id)
        return products

    def list_stocks_by_warehouse(self, *, limit: int = 1000) -> list[dict[str, Any]]:
        """Read current FBS/rFBS stock by seller warehouse.

        The audited v2 contract accepts up to 1000 ``offer_id`` values (or
        ``sku`` values) per request and returns warehouse-level rows with
        cursor/has_next pagination.  We therefore batch the seller catalog
        identifiers instead of issuing one HTTP request per product.

        ``limit`` is the response-page size, not the identifier batch size.
        The identifier batch size is fixed at the confirmed contract maximum
        of 1000; larger catalogs are split into multiple independent requests.
        """
        if limit < 1 or limit > 1000:
            raise ValueError("stock response limit must be in range 1..1000")

        catalog = self._list_product_identifiers(limit=1000)
        offer_ids: list[str] = []
        missing_offer_product_ids: list[str] = []
        seen: set[str] = set()
        for item in catalog:
            offer_id = item.get("offer_id")
            if offer_id not in (None, ""):
                value = str(offer_id)
                if value not in seen:
                    seen.add(value)
                    offer_ids.append(value)
            else:
                pid = item.get("id", item.get("product_id"))
                if pid is not None:
                    missing_offer_product_ids.append(str(pid))

        sku_ids: list[str] = []
        if missing_offer_product_ids:
            # Some catalog responses may omit offer_id. Resolve only those
            # cards through the existing product-info contract and use SKU.
            cards = self.resolve_product_cards(missing_offer_product_ids)
            for pid in missing_offer_product_ids:
                sku = (cards.get(pid) or {}).get("sku")
                if sku not in (None, "") and str(sku) not in seen:
                    seen.add(str(sku))
                    sku_ids.append(str(sku))

        rows: list[dict[str, Any]] = []

        def fetch_identifier_batches(identifiers: list[str], field: str) -> None:
            for start in range(0, len(identifiers), 1000):
                batch = identifiers[start:start + 1000]
                cursor: str | None = None
                while True:
                    payload: dict[str, Any] = {
                        "limit": int(limit),
                        field: batch,
                    }
                    if cursor:
                        payload["cursor"] = cursor
                    data = self._request(
                        "POST",
                        "/v2/product/info/stocks-by-warehouse/fbs",
                        payload,
                    )
                    page = data.get("products") or []
                    if isinstance(page, dict):
                        page = page.get("products") or []
                    if not isinstance(page, list):
                        page = []
                    for raw in page:
                        if not isinstance(raw, dict):
                            continue
                        pid = raw.get("product_id")
                        wid = raw.get("warehouse_id")
                        if pid is None or wid is None:
                            continue
                        rows.append({
                            "row_key": f"{pid}:{wid}",
                            "product_id": str(pid),
                            "sku": str(raw.get("sku")) if raw.get("sku") not in (None, "") else None,
                            "offer_id": str(raw.get("offer_id")) if raw.get("offer_id") not in (None, "") else None,
                            "warehouse_id": int(wid),
                            "warehouse_name": raw.get("warehouse_name"),
                            "present": int(raw.get("present") or 0),
                            "reserved": int(raw.get("reserved") or 0),
                            "free_stock": int(raw.get("free_stock") or 0),
                        })
                    has_next = bool(data.get("has_next"))
                    next_cursor = data.get("cursor")
                    if not has_next or not next_cursor or str(next_cursor) == str(cursor):
                        break
                    cursor = str(next_cursor)

        # The contract says offer_id and sku are alternative selectors; do not
        # send both in one request because the API specifies that sku wins.
        if offer_ids:
            fetch_identifier_batches(offer_ids, "offer_id")
        if sku_ids:
            fetch_identifier_batches(sku_ids, "sku")

        unique = {row["row_key"]: row for row in rows}
        return list(unique.values())

    def update_stocks(self, stocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Update free stock for FBS/rFBS product-warehouse pairs.

        Ozon's current request schema allows 100 product-warehouse pairs per
        request. This is a transport batching rule confirmed by the reviewed
        Ozon-compatible schema; the adapter never retries a mutation.
        """
        if not stocks:
            raise OzonAPIError("No stocks supplied", category="VALIDATION_ERROR")
        results: list[dict[str, Any]] = []
        completed_results: list[dict[str, Any]] = []
        for start in range(0, len(stocks), 100):
            batch = stocks[start:start + 100]
            wire: list[dict[str, Any]] = []
            for item in batch:
                pid = item.get("product_id")
                offer_id = item.get("offer_id")
                if pid in (None, "") and not offer_id:
                    raise OzonAPIError("Stock update requires product_id or offer_id", category="VALIDATION_ERROR")
                stock = int(item.get("stock"))
                if stock < 0:
                    raise OzonAPIError("Stock cannot be negative", category="VALIDATION_ERROR")
                row: dict[str, Any] = {
                    "stock": stock,
                    "warehouse_id": int(item["warehouse_id"]),
                }
                if offer_id:
                    row["offer_id"] = str(offer_id)
                elif pid is not None:
                    row["product_id"] = int(pid)
                wire.append(row)
            try:
                data = self._request("POST", "/v2/products/stocks", {"stocks": wire})
            except Exception as exc:
                setattr(exc, "partial_results", list(completed_results))
                setattr(exc, "failed_batch_offset", start)
                raise
            page = data.get("result") if isinstance(data, dict) else None
            batch_results = page if isinstance(page, list) else []
            completed_results.extend(batch_results)
        return completed_results

    def list_promotions(self) -> list[Promotion]:
        # /v1/actions is the audited source of truth for promotion metadata.
        # In particular, the raw response contains ``auto_add_dates`` for
        # action 1977747. Do not route this read through the optional SDK: its
        # generated model is not the source-of-truth representation and can
        # drop fields that the application needs.
        data = self._request("GET", "/v1/actions")
        rows = data.get("result") or []
        return [Promotion(
            action_id=str(r.get("action_id", r.get("id"))),
            title=str(r.get("title", r.get("name", ""))),
            state=r.get("state") or r.get("status"),
            start_at=r.get("date_start") or r.get("start_at"),
            end_at=r.get("date_end") or r.get("end_at"),
            metadata=r,
        ) for r in rows]

    @staticmethod
    def _normalize_product_ids(product_ids: list[str] | set[str] | tuple[str, ...]) -> list[str]:
        normalized = sorted({str(pid).strip() for pid in product_ids if str(pid).strip()})
        invalid = [pid for pid in normalized if not pid.isdigit()]
        if invalid:
            raise OzonAPIError(
                "Product card lookup requires numeric Ozon Product IDs; "
                f"invalid IDs: {', '.join(invalid[:10])}",
                category="VALIDATION_ERROR",
            )
        return normalized

    def _resolve_product_cards_direct(self, product_ids: list[str]) -> dict[str, dict[str, str | None]]:
        """Resolve product cards through the raw confirmed Ozon HTTP contract.

        We intentionally do not parse this endpoint through ozonapi-async: its
        generated Pydantic response model declares a large set of fields as
        required, while Ozon's live product-info response can omit fields for
        individual cards. One such validation error would discard the entire
        batch even though the raw API response contains usable ``id``, ``name``
        and ``sources[].sku`` values.

        Ozon's current published contract allows up to 1000 identifiers per
        /v3/product/info/list request. We still batch at that confirmed
        boundary so this lookup remains valid when the catalog exceeds 1000
        products.
        """
        result: dict[str, dict[str, str | None]] = {}
        batch_size = self.product_info_batch_size
        for start in range(0, len(product_ids), batch_size):
            batch = product_ids[start:start + batch_size]
            data = self._request(
                "POST",
                "/v3/product/info/list",
                {"product_id": [int(pid) for pid in batch]},
            )
            for item in data.get("items") or []:
                if not isinstance(item, dict):
                    continue
                pid = item.get("id", item.get("product_id"))
                if pid is None:
                    continue
                name = item.get("name")
                sku = item.get("sku")
                if sku in (None, ""):
                    for source in item.get("sources") or []:
                        if isinstance(source, dict) and source.get("sku") not in (None, ""):
                            sku = source.get("sku")
                            break
                result[str(pid)] = {
                    "name": str(name) if name not in (None, "") else None,
                    "sku": str(sku) if sku not in (None, "") else None,
                }
        return result

    def resolve_product_names(self, product_ids: list[str] | set[str] | tuple[str, ...]) -> dict[str, str]:
        """Resolve Product ID -> product-card name through raw Ozon HTTP."""
        normalized = self._normalize_product_ids(product_ids)
        if not normalized:
            return {}
        cards = self._resolve_product_cards_direct(normalized)
        return {pid: card["name"] for pid, card in cards.items() if card.get("name")}

    def resolve_product_cards(self, product_ids: list[str] | set[str] | tuple[str, ...]) -> dict[str, dict[str, str | None]]:
        """Resolve Product ID -> product-card name and SKU through raw Ozon HTTP."""
        normalized = self._normalize_product_ids(product_ids)
        if not normalized:
            return {}
        return self._resolve_product_cards_direct(normalized)

    def list_candidates(self, action_id: str, *, limit: int = 100, last_id: str | None = None) -> dict[str, Any]:
        payload: dict[str, Any] = {"action_id": int(action_id) if str(action_id).isdigit() else action_id, "limit": limit, "last_id": last_id or ""}
        return self._request("POST", "/v2/actions/candidates", payload)

    def list_all_candidates(self, action_id: str, *, limit: int = 100) -> list[dict[str, Any]]:
        """Read all candidate pages without turning candidates into participants."""
        results: list[dict[str, Any]] = []
        cursor: str | None = ""
        while True:
            data = self.list_candidates(action_id, limit=limit, last_id=cursor)
            rows = data.get("products") or []
            results.extend(rows)
            next_cursor = data.get("last_id")
            if not rows or not next_cursor or str(next_cursor) == str(cursor):
                break
            cursor = str(next_cursor)
        return results

    def list_participants(self, action_id: str, *, limit: int = 100, last_id: str | None = None) -> list[ProductState]:
        return self._paginate_products("/v2/actions/products", action_id, limit=limit, last_id=last_id)

    def _paginate_products(self, path: str, action_id: str, *, limit: int = 100, last_id: str | None = None) -> list[ProductState]:
        results: list[ProductState] = []
        cursor = last_id
        while True:
            payload: dict[str, Any] = {"action_id": int(action_id) if str(action_id).isdigit() else action_id, "limit": limit}
            if cursor is not None:
                payload["last_id"] = cursor
            data = self._request("POST", path, payload)
            rows = data.get("products") or []
            results.extend(self._product(action_id, r) for r in rows)
            next_cursor = data.get("last_id")
            if not rows or not next_cursor or str(next_cursor) == str(cursor):
                break
            cursor = str(next_cursor)
        return results

    def read_participants(self, action_id: str, *, limit: int = 100, last_id: str | None = None) -> list[ProductState]:
        return self.list_participants(action_id, limit=limit, last_id=last_id)

    def list_auto_add_products(self, action_id: str, *, auto_add_date: str, limit: int = 100) -> list[dict[str, Any]]:
        """Read all products returned by Ozon Auto-Add for an exact date.

        The date is supplied by Ozon's /v1/actions response; this method never
        invents or defaults it. Pagination uses the documented request fields
        observed in the live API contract: limit + offset.
        """
        if not auto_add_date:
            raise ValueError("auto_add_date is required")
        results: list[dict[str, Any]] = []
        offset = 0
        expected_total: int | None = None
        while True:
            payload = {
                "action_id": int(action_id) if str(action_id).isdigit() else action_id,
                "auto_add_date": auto_add_date,
                "limit": limit,
                "offset": offset,
            }
            data = self._request("POST", "/v1/actions/auto-add/products/list", payload)
            rows = data.get("products") or []
            if expected_total is None and data.get("total") is not None:
                expected_total = int(data["total"])
            results.extend(rows)
            if not rows or len(results) >= (expected_total if expected_total is not None else 0) or len(rows) < limit:
                break
            offset += limit
        # Defensive de-duplication by product_id; Ozon pages must not overlap.
        unique: dict[str, dict[str, Any]] = {}
        for row in results:
            pid = str(row.get("product_id", ""))
            if pid:
                unique[pid] = row
        return list(unique.values())

    def delete_auto_add_products(self, action_id: str, *, auto_add_date: str, product_ids: list[str]) -> MutationResult:
        """Remove products from scheduled Auto-Add for the supplied date.

        Contract source: current Ozon-compatible SDK model requires
        action_id + auto_add_date + product_ids and returns product_ids.
        The application performs Fresh Check, Snapshot and read-after-write
        reconciliation around this transport call; this adapter never retries
        the mutation itself.
        """
        ids = [str(pid) for pid in product_ids]
        if not auto_add_date:
            raise OzonAPIError("auto_add_date is required", category="VALIDATION_ERROR")
        if not ids:
            raise OzonAPIError("No products supplied for Auto-Add deletion", category="VALIDATION_ERROR")
        if len(ids) != len(set(ids)):
            raise OzonAPIError("Duplicate product_id in Auto-Add deletion", category="VALIDATION_ERROR")
        payload = {
            "action_id": int(action_id) if str(action_id).isdigit() else action_id,
            "auto_add_date": auto_add_date,
            "product_ids": [int(pid) if pid.isdigit() else pid for pid in ids],
        }
        data, status = self._request("POST", "/v1/actions/auto-add/products/delete", payload, return_status=True)
        returned = data.get("product_ids") if isinstance(data, dict) else None
        if returned is None and isinstance(data, dict) and isinstance(data.get("result"), dict):
            returned = data["result"].get("product_ids")
        return MutationResult(
            deactivated_product_ids=tuple(str(x) for x in (returned or [])),
            transport_status=status,
        )

    def update_auto_add_products(self, action_id: str, *, auto_add_date: str, products: list[dict[str, Any]]) -> MutationResult:
        """Add or update products in scheduled Auto-Add.

        Contract source: current Ozon-compatible SDK exposes
        POST /v2/actions/auto-add/products/update with action_id, auto_add_date
        and products[{id, action_price, optional stock}]. This contract is
        implemented but remains LIVE_VERIFICATION_UNKNOWN until a controlled
        real-account mutation confirms the endpoint in this project.
        """
        if not auto_add_date:
            raise OzonAPIError("auto_add_date is required", category="VALIDATION_ERROR")
        if not products:
            raise OzonAPIError("No products supplied for Auto-Add update", category="VALIDATION_ERROR")
        ids: list[str] = []
        seen: set[str] = set()
        wire_products: list[dict[str, Any]] = []
        for item in products:
            pid = str(item.get("product_id", item.get("id", ""))).strip()
            if not pid or not pid.isdigit():
                raise OzonAPIError(f"Invalid Auto-Add product ID: {pid}", category="VALIDATION_ERROR")
            if pid in seen:
                raise OzonAPIError(f"Duplicate product_id in Auto-Add update: {pid}", category="VALIDATION_ERROR")
            seen.add(pid)
            price = self._money(item.get("action_price"))
            if price is None or price < 0:
                raise OzonAPIError(f"Invalid action_price for Auto-Add product {pid}", category="VALIDATION_ERROR")
            ids.append(pid)
            product_wire: dict[str, Any] = {
                "id": int(pid),
                "action_price": {"amount": str(price), "currency": str(item.get("currency") or "RUB")},
            }
            if item.get("stock") is not None:
                product_wire["stock"] = int(item["stock"])
            wire_products.append(product_wire)

        payload = {
            "action_id": int(action_id) if str(action_id).isdigit() else action_id,
            "auto_add_date": auto_add_date,
            "products": wire_products,
        }
        data, status = self._request("POST", "/v2/actions/auto-add/products/update", payload, return_status=True)
        if not isinstance(data, dict):
            data = {}
        return MutationResult(
            active_product_ids=tuple(str(x) for x in (data.get("product_ids") or [])),
            deactivated_product_ids=tuple(str(x) for x in (data.get("deactivated_ids") or [])),
            rejected=tuple(data.get("rejected") or []),
            warnings=tuple(data.get("warnings") or []),
            transport_status=status,
        )

    def list_auto_add_candidates(self, action_id: str, *, auto_add_date: str, limit: int = 100) -> list[dict[str, Any]]:
        """Read Auto-Add candidates for the exact Ozon-provided date."""
        if not auto_add_date:
            raise ValueError("auto_add_date is required")
        results: list[dict[str, Any]] = []
        offset = 0
        while True:
            payload = {
                "action_id": int(action_id) if str(action_id).isdigit() else action_id,
                "auto_add_date": auto_add_date,
                "limit": limit,
                "offset": offset,
            }
            data = self._request("POST", "/v1/actions/auto-add/products/candidates", payload)
            rows = data.get("products") or []
            results.extend(rows)
            total = data.get("total")
            if not rows or (total is not None and len(results) >= int(total)) or len(rows) < limit:
                break
            offset += limit
        return results

    def activate_products(self, action_id: str, product_ids: list[str], prices: dict[str, Any] | None = None, stocks: dict[str, int] | None = None) -> MutationResult:
        """Activate products and/or set action_price for already participating products.

        Live-verified for an existing Elastic Boosting participant: Ozon accepted
        this endpoint and changed action_price on read-after-write. The public
        contract describes the operation as activation, so the application keeps
        membership classification outside the transport adapter.
        """
        ids = [str(pid) for pid in product_ids]
        if not ids:
            raise OzonAPIError("No products supplied for activation", category="VALIDATION_ERROR")
        prices = prices or {}
        stocks = stocks or {}
        products: list[dict[str, Any]] = []
        for pid in ids:
            if pid not in prices:
                raise OzonAPIError(f"Missing action_price for product {pid}", category="VALIDATION_ERROR")
            item: dict[str, Any] = {
                "product_id": int(pid) if pid.isdigit() else pid,
                "action_price": OzonPromotionsAdapter._json_number(prices[pid]),
            }
            if pid in stocks and stocks[pid] is not None:
                item["stock"] = int(stocks[pid])
            products.append(item)
        payload = {
            "action_id": int(action_id) if str(action_id).isdigit() else action_id,
            "products": products,
        }
        data, status = self._request("POST", "/v1/actions/products/activate", payload, return_status=True)
        result = data.get("result") if isinstance(data, dict) else None
        if not isinstance(result, dict):
            result = data if isinstance(data, dict) else {}
        return MutationResult(
            active_product_ids=tuple(str(x) for x in (result.get("product_ids") or [])),
            rejected=tuple(result.get("rejected") or []),
            transport_status=status,
        )

    def deactivate_products(self, action_id: str, product_ids: list[str]) -> MutationResult:
        ids = [str(pid) for pid in product_ids]
        if not ids:
            raise OzonAPIError("No products supplied for deactivation", category="VALIDATION_ERROR")
        payload = {
            "action_id": int(action_id) if str(action_id).isdigit() else action_id,
            "product_ids": [int(pid) if pid.isdigit() else pid for pid in ids],
        }
        data, status = self._request("POST", "/v1/actions/products/deactivate", payload, return_status=True)
        result = data.get("result") if isinstance(data, dict) else None
        if not isinstance(result, dict):
            result = data if isinstance(data, dict) else {}
        return MutationResult(
            deactivated_product_ids=tuple(str(x) for x in (result.get("product_ids") or [])),
            rejected=tuple(result.get("rejected") or []),
            transport_status=status,
        )

    def update_products(self, action_id: str, products: list[dict[str, Any]]) -> MutationResult:
        """Update action_price for existing participants via the live-verified activate contract.

        The old /v1/actions/products/update endpoint is intentionally not called:
        it was not confirmed in the current API catalog. Existing participants are
        updated through /v1/actions/products/activate, which was verified live.
        """
        if not products:
            raise OzonAPIError("Mutation products must not be empty", category="VALIDATION_ERROR")
        prices: dict[str, Any] = {}
        stocks: dict[str, int] = {}
        ids: list[str] = []
        seen: set[str] = set()
        for item in products:
            product_id = str(item["product_id"])
            if product_id in seen:
                raise OzonAPIError(f"Duplicate product_id in mutation batch: {product_id}", category="VALIDATION_ERROR")
            seen.add(product_id)
            ids.append(product_id)
            prices[product_id] = item["action_price"]
            if item.get("stock") is not None:
                stocks[product_id] = int(item["stock"])
        return self.activate_products(action_id, ids, prices=prices, stocks=stocks)

