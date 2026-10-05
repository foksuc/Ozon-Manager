from __future__ import annotations

from dataclasses import replace
from decimal import Decimal
from typing import Iterable

from app.domain.models import MutationResult, ProductState, Promotion


class MockOzonAdapter:
    def __init__(self, promotions: Iterable[Promotion], products: Iterable[ProductState]):
        self.promotions = list(promotions)
        self.products = {p.product_id: p for p in products}
        self.fail_ids: set[str] = set()
        self.warning_ids: set[str] = set()
        self.timeout = False
        self.mutation_timeout = False
        self.mutation_unknown_after_apply = False
        self.verify_mismatch_ids: set[str] = set()
        self.update_calls: list[list[str]] = []
        self.stock_rows: dict[str, dict] = {}


    def list_stocks_by_warehouse(self, **kwargs):
        rows = []
        for p in self.products.values():
            key = f"{p.product_id}:1001"
            row = self.stock_rows.get(key, {
                "row_key": key, "product_id": str(p.product_id), "sku": str(p.product_id),
                "offer_id": p.offer_id, "warehouse_id": 1001, "warehouse_name": "Mock FBS warehouse",
                "present": 10, "reserved": 2, "free_stock": 8,
            })
            rows.append(dict(row))
        return rows

    def update_stocks(self, stocks):
        results = []
        for item in stocks:
            pid = str(item.get("product_id"))
            stock = int(item.get("stock", 0))
            wid = int(item["warehouse_id"])
            key = f"{pid}:{wid}"
            existing = self.stock_rows.get(key, {"row_key": key, "product_id": pid, "sku": pid, "offer_id": item.get("offer_id"), "warehouse_id": wid, "warehouse_name": "Mock FBS warehouse", "present": 10, "reserved": 2, "free_stock": 8})
            existing = dict(existing)
            existing["free_stock"] = stock
            existing["present"] = stock + int(existing.get("reserved", 0))
            self.stock_rows[key] = existing
            results.append({
                "warehouse_id": wid, "product_id": int(pid), "offer_id": item.get("offer_id"),
                "updated": True, "errors": [],
            })
        return results

    def list_promotions(self):
        return self.promotions

    def resolve_product_names(self, product_ids):
        return {str(pid): self.products[str(pid)].name for pid in product_ids if str(pid) in self.products and self.products[str(pid)].name}

    def resolve_product_cards(self, product_ids):
        return {
            str(pid): {
                "name": self.products[str(pid)].name,
                # Mock has no separate Ozon catalog SKU field; use the stable
                # mock product identifier so the UI selection flow remains testable.
                "sku": str(pid),
            }
            for pid in product_ids
            if str(pid) in self.products
        }

    def list_candidates(self, action_id, **kwargs):
        return {"products": [p.__dict__ for p in self.products.values() if p.action_id == str(action_id)]}

    def list_all_candidates(self, action_id, **kwargs):
        return [p.__dict__ for p in self.products.values() if p.action_id == str(action_id)]

    def list_participants(self, action_id, **kwargs):
        return [p for p in self.products.values() if p.action_id == str(action_id) and (p.membership or "active") == "active"]

    def read_participants(self, action_id, **kwargs):
        if self.timeout:
            raise RuntimeError("UNKNOWN_RESULT")

        mutated_ids = {
            pid
            for batch in self.update_calls
            for pid in batch
        }

        result = []
        for p in self.products.values():
            if p.action_id != str(action_id) or (p.membership or "active") != "active":
                continue

            if p.product_id in self.verify_mismatch_ids and p.product_id in mutated_ids:
                result.append(
                    replace(
                        p,
                        action_price=p.action_price + Decimal("1"),
                    )
                )
            else:
                result.append(p)

        return result
        
    def activate_products(self, action_id, product_ids, prices=None, stocks=None):
        prices = prices or {}
        active, rejected = [], []
        for pid in map(str, product_ids):
            if pid not in self.products:
                rejected.append({"product_id": pid, "reason": "unknown product"})
                continue
            p = self.products[pid]
            if pid not in prices:
                rejected.append({"product_id": pid, "reason": "missing action_price"})
                continue
            self.products[pid] = replace(
                p, membership="active", action_price=Decimal(str(prices[pid]))
            )
            active.append(pid)
        return MutationResult(tuple(active), (), tuple(rejected), (), 200)

    def deactivate_products(self, action_id, product_ids):
        active = []
        rejected = []
        for pid in map(str, product_ids):
            if pid in self.products:
                self.products[pid] = replace(self.products[pid], membership="inactive")
                active.append(pid)
            else:
                rejected.append({"product_id": pid, "reason": "unknown product"})
        return MutationResult((), tuple(active), tuple(rejected), (), 200)

    def update_products(self, action_id, products):
        if self.mutation_timeout:
            raise RuntimeError("UNKNOWN_RESULT")
        active, rejected, warnings = [], [], []
        self.update_calls.append([str(item["product_id"]) for item in products])
        for item in products:
            pid = str(item["product_id"])
            if pid in self.fail_ids:
                rejected.append({"product_id": pid, "reason": "mock rejection"})
                continue
            old = self.products[pid]
            self.products[pid] = replace(old, action_price=Decimal(str(item["action_price"])))
            active.append(pid)
            if pid in self.warning_ids:
                warnings.append({"product_id": pid, "message": "mock warning"})
        if self.mutation_unknown_after_apply:
            raise RuntimeError("UNKNOWN_RESULT")
        return MutationResult(tuple(active), (), tuple(rejected), tuple(warnings), 200)
