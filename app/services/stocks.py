from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Callable
import uuid

from app.adapters.ozon import OzonAPIError


@dataclass(frozen=True)
class StockChange:
    product_id: str
    sku: str | None
    offer_id: str | None
    warehouse_id: int
    warehouse_name: str | None
    old_present: int
    old_reserved: int
    old_free_stock: int
    requested_free_stock: int
    updated_at: str | None = None

    @property
    def key(self) -> str:
        return f"{self.product_id}:{self.warehouse_id}"


class StockService:
    """Safety boundary for the independent Stocks workflow.

    The service never retries a stock mutation. Every execution performs a fresh
    read, persists a pre-mutation snapshot, then calls the adapter and reconciles
    each returned product/warehouse pair with a read-after-write.
    """

    def __init__(self, adapter, repository):
        self.adapter = adapter
        self.repository = repository

    @staticmethod
    def normalize_changes(changes: list[StockChange]) -> list[StockChange]:
        seen: set[str] = set()
        result: list[StockChange] = []
        for change in changes:
            if change.requested_free_stock < 0:
                raise ValueError(f"Остаток не может быть отрицательным: {change.key}")
            if change.key in seen:
                raise ValueError(f"Дубликат товар–склад: {change.key}")
            seen.add(change.key)
            result.append(change)
        if not result:
            raise ValueError("Нет изменений для отправки")
        return result

    @staticmethod
    def fresh_diff(expected: StockChange, actual: dict[str, Any] | None) -> str | None:
        if actual is None:
            return "Товар–склад больше не найден в актуальном ответе Ozon"
        actual_free = int(actual.get("free_stock") or 0)
        actual_present = int(actual.get("present") or 0)
        actual_reserved = int(actual.get("reserved") or 0)
        if actual_free != expected.old_free_stock or actual_present != expected.old_present or actual_reserved != expected.old_reserved:
            return (
                f"остаток изменился: было present={expected.old_present}, reserved={expected.old_reserved}, "
                f"free={expected.old_free_stock}; сейчас present={actual_present}, reserved={actual_reserved}, free={actual_free}"
            )
        return None

    def _fresh_map(self, changes: list[StockChange]) -> dict[str, dict[str, Any]]:
        latest = self.adapter.list_stocks_by_warehouse()
        return {str(row["row_key"]): row for row in latest if row.get("row_key")}

    def prepare(self, changes: list[StockChange]) -> dict[str, Any]:
        normalized = self.normalize_changes(changes)
        current = self._fresh_map(normalized)
        mismatches = []
        for change in normalized:
            diff = self.fresh_diff(change, current.get(change.key))
            if diff:
                mismatches.append({"key": change.key, "product_id": change.product_id, "warehouse_id": change.warehouse_id, "reason": diff})
        if mismatches:
            raise ValueError("Fresh Check не пройден. Обновите данные и пересчитайте изменения.")
        snapshot_id = uuid.uuid4().hex
        operation_id = uuid.uuid4().hex
        self.repository.create_stock_operation(
            operation_id=operation_id,
            operation_type="UPDATE_STOCK",
            status="PREVIEWED",
            product_count=len(normalized),
            snapshot_id=snapshot_id,
        )
        self.repository.save_stock_snapshot(snapshot_id, operation_id, normalized)
        self.repository.update_stock_operation_status(operation_id, "SNAPSHOTTED")
        return {
            "operation_id": operation_id,
            "snapshot_id": snapshot_id,
            "changes": normalized,
            "fresh": current,
        }

    def prepare_rollback(self, snapshot_id: str) -> dict[str, Any]:
        """Prepare rollback as a new mutation from an immutable stock snapshot.

        The snapshot is the target state; the current Ozon state is the source
        state. A new snapshot is created by ``prepare`` so rollback itself has
        the same safety/audit trail as an ordinary mutation.
        """
        snapshot_rows = [dict(r) for r in self.repository.get_stock_snapshot(snapshot_id)]
        if not snapshot_rows:
            raise ValueError("Stock snapshot not found")
        current = self._fresh_map([
            StockChange(
                product_id=str(r["product_id"]), sku=r["sku"], offer_id=r["offer_id"],
                warehouse_id=int(r["warehouse_id"]), warehouse_name=r["warehouse_name"],
                old_present=int(r["present"]), old_reserved=int(r["reserved"]),
                old_free_stock=int(r["free_stock"]), requested_free_stock=int(r["free_stock"]),
            ) for r in snapshot_rows
        ])
        changes: list[StockChange] = []
        for r in snapshot_rows:
            key = f"{r['product_id']}:{r['warehouse_id']}"
            row = current.get(key)
            if row is None:
                raise ValueError(f"Rollback Fresh Check: товар–склад не найден: {key}")
            changes.append(StockChange(
                product_id=str(r["product_id"]), sku=r["sku"], offer_id=r["offer_id"],
                warehouse_id=int(r["warehouse_id"]), warehouse_name=r["warehouse_name"],
                old_present=int(row["present"]), old_reserved=int(row["reserved"]),
                old_free_stock=int(row["free_stock"]),
                requested_free_stock=int(r["free_stock"]), updated_at=row.get("updated_at"),
            ))
        # prepare() performs the second Fresh Check and snapshots the current
        # state immediately before the rollback mutation.
        return self.prepare(changes)

    def execute(self, plan: dict[str, Any], *, confirmed: bool) -> dict[str, Any]:
        if not confirmed:
            raise ValueError("Массовое изменение остатков требует явного подтверждения")
        operation_id = str(plan.get("operation_id") or "")
        snapshot_id = str(plan.get("snapshot_id") or "")
        if not operation_id or not snapshot_id:
            raise ValueError("Mutation требует operation_id и snapshot_id")
        operation = self.repository.get_stock_operation(operation_id)
        if operation is None:
            raise ValueError("Stock operation не найдена")
        if str(operation["snapshot_id"] or "") != snapshot_id:
            raise ValueError("Snapshot не соответствует операции")
        if not self.repository.get_stock_snapshot(snapshot_id):
            raise ValueError("Snapshot отсутствует; mutation запрещена")
        terminal_statuses = {"SUCCESS", "PARTIAL", "FAILED", "UNKNOWN_RESULT"}
        if str(operation["status"]) in terminal_statuses:
            raise ValueError(f"Операция уже завершена: {operation['status']}")
        changes = self.normalize_changes(list(plan["changes"]))
        current = self._fresh_map(changes)
        mismatches = []
        for change in changes:
            diff = self.fresh_diff(change, current.get(change.key))
            if diff:
                mismatches.append({"key": change.key, "reason": diff})
        if mismatches:
            self.repository.update_stock_operation_status(plan["operation_id"], "FAILED", error_summary="Fresh Check перед mutation не пройден")
            raise ValueError("Fresh Check перед изменением не пройден. Обновите данные и пересчитайте изменения.")

        self.repository.update_stock_operation_status(plan["operation_id"], "CONFIRMED")
        payload = [
            {
                "product_id": int(c.product_id),
                "warehouse_id": int(c.warehouse_id),
                "stock": int(c.requested_free_stock),
                **({"offer_id": c.offer_id} if c.offer_id else {}),
            }
            for c in changes
        ]
        self.repository.update_stock_operation_status(plan["operation_id"], "RUNNING")
        try:
            results = self.adapter.update_stocks(payload)
        except Exception as exc:
            partial_results = list(getattr(exc, "partial_results", []) or [])
            partial_by_key = {f"{r.get('product_id')}:{r.get('warehouse_id')}": r for r in partial_results}
            for c in changes:
                partial = partial_by_key.get(c.key)
                if partial and bool(partial.get("updated")):
                    self.repository.save_stock_item_result(plan["operation_id"], c, status="SUCCESS")
                elif partial:
                    errors = partial.get("errors") or []
                    msg = "; ".join(str(e.get("message") or e.get("code") or e) for e in errors) or "Ozon отклонил обновление"
                    self.repository.save_stock_item_result(plan["operation_id"], c, status="FAILED", error=msg)
                else:
                    self.repository.save_stock_item_result(plan["operation_id"], c, status="UNKNOWN_RESULT", error=str(exc))
            self.repository.update_stock_operation_status(plan["operation_id"], "UNKNOWN_RESULT", error_summary=str(exc))
            if isinstance(exc, OzonAPIError):
                raise
            raise RuntimeError(f"Результат mutation неизвестен: {getattr(exc, 'category', 'UNKNOWN_RESULT')}") from exc

        by_key = {f"{r.get('product_id')}:{r.get('warehouse_id')}": r for r in results}
        success = failed = 0
        for c in changes:
            result = by_key.get(c.key)
            if not result:
                self.repository.save_stock_item_result(plan["operation_id"], c, status="FAILED", error="Ozon не вернул результат по товару–складу")
                failed += 1
                continue
            if not bool(result.get("updated")):
                errors = result.get("errors") or []
                message = "; ".join(str(e.get("message") or e.get("code") or e) for e in errors) or "Ozon отклонил обновление"
                self.repository.save_stock_item_result(plan["operation_id"], c, status="FAILED", error=message)
                failed += 1
                continue
            success += 1
            self.repository.save_stock_item_result(plan["operation_id"], c, status="SUCCESS")

        # Read-after-write reconciliation. No mutation retry is attempted.
        # If the verification read itself fails, the mutation outcome is not
        # safe to call SUCCESS: Ozon may have accepted the write while the
        # verification response was lost. Persist an explicit UNKNOWN_RESULT
        # state and never retry the mutation automatically.
        try:
            latest = self._fresh_map(changes)
        except Exception as exc:
            rows = self.repository.list_stock_operation_items(plan["operation_id"])
            for row in rows:
                row_dict = dict(row)
                if row_dict.get("status") == "SUCCESS":
                    change = next((c for c in changes if c.key == row_dict["row_key"]), None)
                    if change is not None:
                        self.repository.save_stock_item_result(
                            plan["operation_id"], change, status="UNKNOWN_RESULT",
                            error=f"Read-after-write failed; mutation outcome may be unknown: {exc}",
                        )
            self.repository.update_stock_operation_status(
                plan["operation_id"], "UNKNOWN_RESULT",
                error_summary=f"Read-after-write failed; mutation outcome may be unknown: {exc}",
            )
            raise RuntimeError("Результат mutation неизвестен: не удалось выполнить read-after-write проверку") from exc

        rows_before_verification = {dict(r)["row_key"]: dict(r) for r in self.repository.list_stock_operation_items(plan["operation_id"])}
        for c in changes:
            # Only an item that Ozon explicitly accepted (`updated=true`) is
            # eligible for read-after-write verification. A missing/rejected
            # API result is already a terminal FAILED state and must not be
            # overwritten by observing the unchanged old stock.
            if rows_before_verification.get(c.key, {}).get("status") != "SUCCESS":
                continue
            row = latest.get(c.key)
            if row is None:
                self.repository.save_stock_item_result(
                    plan["operation_id"], c, status="VERIFICATION_FAILED",
                    error="После mutation товар–склад не найден", actual=None,
                )
                continue
            actual = {
                "present": int(row.get("present") or 0),
                "reserved": int(row.get("reserved") or 0),
                "free_stock": int(row.get("free_stock") or 0),
            }
            if actual["free_stock"] != c.requested_free_stock:
                self.repository.save_stock_item_result(
                    plan["operation_id"], c, status="VERIFICATION_FAILED",
                    error=f"Read-after-write: free_stock={actual['free_stock']}, ожидалось {c.requested_free_stock}",
                    actual=actual,
                )
            else:
                self.repository.save_stock_item_result(
                    plan["operation_id"], c, status="SUCCESS", actual=actual,
                )

        rows = self.repository.list_stock_operation_items(plan["operation_id"])
        verified_success = sum(1 for r in rows if r["status"] == "SUCCESS")
        verification_failed = sum(1 for r in rows if r["status"] == "VERIFICATION_FAILED")
        final_failed = len(changes) - verified_success
        status = "SUCCESS" if final_failed == 0 else ("PARTIAL" if verified_success > 0 else "FAILED")
        self.repository.update_stock_operation_status(
            plan["operation_id"], status, success_count=verified_success, failed_count=final_failed,
            error_summary=(f"Проверка после mutation: {verification_failed} ошибок" if verification_failed else None),
        )
        return {
            "operation_id": plan["operation_id"],
            "snapshot_id": plan["snapshot_id"],
            "status": status,
            "success_count": verified_success,
            "failed_count": final_failed,
            "items": self.repository.list_stock_operation_items(plan["operation_id"]),
        }
