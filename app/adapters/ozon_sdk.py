from __future__ import annotations

import asyncio
from typing import Any, Iterable

from app.domain.models import Promotion


class OzonSDKError(RuntimeError):
    """Raised when the optional OzonAPI SDK read adapter cannot complete."""


class OzonSDKPromotionsReader:
    """Small SDK boundary for a confirmed read-only operation.

    Only /v1/actions is delegated to OzonAPI. Candidate/participant reads and
    mutations stay in the direct adapter because the audited SDK models do not
    preserve the richer product-level fields required by this application.
    """

    def __init__(self, client_id: str, api_key: str):
        self.client_id = client_id
        self.api_key = api_key

    @staticmethod
    async def _fetch(client_id: str, api_key: str) -> dict[str, Any]:
        try:
            from ozonapi.seller import SellerAPI, SellerAPIConfig
        except ImportError as exc:
            raise OzonSDKError(
                "OzonAPI SDK is not installed; install ozonapi-async before enabling SDK reads"
            ) from exc

        try:
            config = SellerAPIConfig(client_id=client_id, api_key=api_key)
            async with SellerAPI(config=config) as api:
                response = await api.actions()
                if hasattr(response, "model_dump"):
                    return response.model_dump()
                if isinstance(response, dict):
                    return response
                raise TypeError(f"Unsupported OzonAPI actions response type: {type(response)!r}")
        except OzonSDKError:
            raise
        except Exception as exc:
            raise OzonSDKError(f"OzonAPI SDK /v1/actions failed: {type(exc).__name__}") from exc

    def list_promotions(self) -> list[Promotion]:
        data = asyncio.run(self._fetch(self.client_id, self.api_key))
        rows = data.get("result") or []
        promotions: list[Promotion] = []
        for row in rows:
            promotions.append(
                Promotion(
                    action_id=str(row.get("action_id", row.get("id"))),
                    title=str(row.get("title", row.get("name", ""))),
                    state=row.get("state") or row.get("status"),
                    start_at=row.get("date_start") or row.get("start_at"),
                    end_at=row.get("date_end") or row.get("end_at"),
                    metadata=dict(row),
                )
            )
        return promotions

    @staticmethod
    async def _fetch_product_cards(client_id: str, api_key: str, product_ids: list[int]) -> dict[str, dict[str, str | None]]:
        try:
            from ozonapi.seller import SellerAPI, SellerAPIConfig
            from ozonapi.seller.schemas.products import ProductInfoListRequest
        except ImportError as exc:
            raise OzonSDKError(
                "OzonAPI SDK product-info support is not installed; install ozonapi-async"
            ) from exc

        try:
            config = SellerAPIConfig(client_id=client_id, api_key=api_key)
            async with SellerAPI(config=config) as api:
                request = ProductInfoListRequest(product_id=product_ids)
                response = await api.product_info_list(request)
                if hasattr(response, "model_dump"):
                    data = response.model_dump()
                elif isinstance(response, dict):
                    data = response
                else:
                    raise TypeError(
                        f"Unsupported OzonAPI product_info_list response type: {type(response)!r}"
                    )

                result: dict[str, dict[str, str | None]] = {}
                for item in data.get("items") or []:
                    if not isinstance(item, dict):
                        continue
                    product_id = item.get("id", item.get("product_id"))
                    if product_id is None:
                        continue
                    name = item.get("name")
                    # Ozon /v3/product/info/list returns the card SKU inside
                    # ``sources[].sku``.  It is not a top-level ``sku`` field.
                    # Keep a top-level fallback for compatibility with older
                    # SDK/mock response shapes, but prefer the actual Ozon
                    # product-info contract.
                    sku = item.get("sku")
                    if sku in (None, ""):
                        sources = item.get("sources") or []
                        if isinstance(sources, list):
                            for source in sources:
                                if isinstance(source, dict) and source.get("sku") not in (None, ""):
                                    sku = source.get("sku")
                                    break
                    result[str(product_id)] = {
                        "name": str(name) if name not in (None, "") else None,
                        "sku": str(sku) if sku not in (None, "") else None,
                    }
                return result
        except OzonSDKError:
            raise
        except Exception as exc:
            raise OzonSDKError(
                f"OzonAPI SDK /v3/product/info/list failed: {type(exc).__name__}"
            ) from exc

    def resolve_product_names(self, product_ids: Iterable[str]) -> dict[str, str]:
        """Resolve Ozon product IDs to product-card names through OzonAPI SDK.

        The SDK request is deliberately made with the complete unique ID set.
        No undocumented batch-size assumption is encoded here. If Ozon's
        current contract requires batching, it must be established separately
        and then configured explicitly.
        """
        normalized = sorted({str(pid) for pid in product_ids if str(pid).strip()})
        if not normalized:
            return {}
        invalid = [pid for pid in normalized if not pid.isdigit()]
        if invalid:
            raise OzonSDKError(
                "Product name lookup requires numeric Ozon Product IDs; "
                f"invalid IDs: {', '.join(invalid[:10])}"
            )
        cards = asyncio.run(
            self._fetch_product_cards(
                self.client_id,
                self.api_key,
                [int(pid) for pid in normalized],
            )
        )
        return {pid: card["name"] for pid, card in cards.items() if card.get("name")}

    def resolve_product_cards(self, product_ids: Iterable[str]) -> dict[str, dict[str, str | None]]:
        """Resolve Product ID -> product-card name/SKU through the read-only SDK path."""
        normalized = sorted({str(pid) for pid in product_ids if str(pid).strip()})
        if not normalized:
            return {}
        invalid = [pid for pid in normalized if not pid.isdigit()]
        if invalid:
            raise OzonSDKError(
                "Product card lookup requires numeric Ozon Product IDs; "
                f"invalid IDs: {', '.join(invalid[:10])}"
            )
        return asyncio.run(
            self._fetch_product_cards(
                self.client_id,
                self.api_key,
                [int(pid) for pid in normalized],
            )
        )
