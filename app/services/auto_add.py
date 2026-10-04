from __future__ import annotations

from decimal import Decimal
from typing import Any

from app.domain.models import ItemStatus, Operation, OperationItem, OperationStatus, ProductState, utc_now
from app.domain.state_machine import transition
from app.services.workflow import OperationFactory, SnapshotService


SAFETY_FIELDS = (
    "price",
    "action_price_to_auto_add",
    "min_seller_price",
    "max_discount_price",
    "marketplace_seller_price",
    "quantity_to_auto_add",
    "min_action_quantity",
    "add_mode",
)


def _money(row: dict[str, Any], key: str) -> Decimal | None:
    value = row.get(key)
    if isinstance(value, dict):
        value = value.get("amount")
    if value in (None, ""):
        return None
    try:
        return Decimal(str(value))
    except Exception:
        return None


def _pid(row: dict[str, Any]) -> str:
    value = row.get("product_id", row.get("id"))
    if value in (None, ""):
        return ""
    return str(value)


def _same_value(a: Any, b: Any) -> bool:
    if a is None or a == "":
        return b is None or b == ""
    if b is None or b == "":
        return False
    try:
        return Decimal(str(a)) == Decimal(str(b))
    except Exception:
        return str(a) == str(b)


def row_safety_diffs(expected: dict[str, Any], actual: dict[str, Any]) -> list[str]:
    diffs: list[str] = []
    for field in SAFETY_FIELDS:
        if field not in expected:
            continue
        if not _same_value(expected.get(field), actual.get(field)):
            diffs.append(field)
    return diffs


def row_to_product_state(action_id: str, row: dict[str, Any]) -> ProductState:
    pid = _pid(row)
    return ProductState(
        action_id=str(action_id),
        product_id=pid,
        offer_id=str(row["offer_id"]) if row.get("offer_id") is not None else None,
        name=row.get("name"),
        price=_money(row, "price"),
        action_price=_money(row, "action_price_to_auto_add") or Decimal("0"),
        current_boost=None,
        min_boost=None,
        max_boost=None,
        price_min_elastic=None,
        price_max_elastic=_money(row, "max_discount_price"),
        membership="auto_add",
        availability=None,
        currency=str(row.get("currency") or "RUB"),
    )


class AutoAddDeleteService:
    """Safe mutation service for removing products from Ozon scheduled Auto-Add."""

    def __init__(self, adapter, repository):
        self.adapter = adapter
        self.repository = repository
        self.snapshot_service = SnapshotService(repository)

    def build_operation(
        self,
        action_id: str,
        auto_add_date: str,
        rows: list[dict[str, Any]],
        threshold: Decimal,
        user: str,
    ) -> Operation:
        if not auto_add_date:
            raise ValueError("Auto-Add date is UNKNOWN; deletion is blocked")
        if not threshold.is_finite():
            raise ValueError("Порог скидки должен быть конечным числом")

        selected = [r for r in rows if (lambda d: d is not None and d > threshold)(self._discount(r))]
        if not selected:
            raise ValueError("Нет товаров со скидкой выше указанного порога")

        ids = [_pid(r) for r in selected]
        if any(not pid for pid in ids):
            raise ValueError("У одного или нескольких товаров отсутствует product_id")
        if len(ids) != len(set(ids)):
            raise ValueError("В Auto-Add обнаружены дубли product_id; mutation заблокирована")

        op = OperationFactory.create(action_id, user, operation_type="AUTO_ADD_DELETE")
        op.items = [
            OperationItem(
                operation_id=op.operation_id,
                product_id=_pid(row),
                old_action_price=_money(row, "action_price_to_auto_add") or Decimal("0"),
                requested_action_price=Decimal("0"),
            )
            for row in selected
        ]
        op.request_fingerprint = OperationFactory.fingerprint(
            action_id,
            [(auto_add_date, i.product_id) for i in op.items],
            f"AUTO_ADD_DELETE:{threshold}",
        )
        op.status = transition(op.status, OperationStatus.PREVIEWED)
        return op

    @staticmethod
    def _discount(row: dict[str, Any]) -> Decimal | None:
        price = _money(row, "price")
        action_price = _money(row, "action_price_to_auto_add")
        if price is None or price == 0 or action_price is None:
            return None
        return (price - action_price) / price * Decimal("100")

    def execute(
        self,
        operation: Operation,
        auto_add_date: str,
        preview_rows: dict[str, dict[str, Any]],
        user: str,
    ) -> tuple[Operation, Any]:
        if operation.status != OperationStatus.PREVIEWED:
            raise ValueError("Auto-Add deletion requires Preview")

        ids = [item.product_id for item in operation.items]
        fresh_rows = self.adapter.list_auto_add_products(operation.action_id, auto_add_date=auto_add_date, limit=100)
        fresh = {_pid(row): row for row in fresh_rows}

        missing = [pid for pid in ids if pid not in fresh]
        changed = []
        for pid in ids:
            if pid in fresh and pid in preview_rows:
                diffs = row_safety_diffs(preview_rows[pid], fresh[pid])
                if diffs:
                    changed.append(f"{pid}: {', '.join(diffs)}")
        if missing or changed:
            operation.status = OperationStatus.FAILED
            operation.error_summary = (
                "Fresh Check Auto-Add не пройден: "
                f"missing={missing}; changed={changed}. Требуется refresh/recalculate."
            )
            operation.completed_at = utc_now()
            self.repository.save_operation(operation)
            raise RuntimeError(operation.error_summary)

        current_states = {pid: row_to_product_state(operation.action_id, fresh[pid]) for pid in ids}
        operation.status = transition(operation.status, OperationStatus.FRESH_CHECKED)
        self.repository.save_operation(operation)
        self.snapshot_service.create(operation, current_states, auto_add_date=auto_add_date)
        operation.confirmation_at = utc_now()
        operation.requested_by_user = user
        operation.status = transition(operation.status, OperationStatus.CONFIRMED)
        self.repository.save_operation(operation)

        # Final read immediately before the mutation. No mutation is retried.
        final_rows = self.adapter.list_auto_add_products(operation.action_id, auto_add_date=auto_add_date, limit=100)
        final_map = {_pid(row): row for row in final_rows}
        final_missing = [pid for pid in ids if pid not in final_map]
        final_changed = []
        for pid in ids:
            if pid in final_map:
                diffs = row_safety_diffs(preview_rows[pid], final_map[pid])
                if diffs:
                    final_changed.append(f"{pid}: {', '.join(diffs)}")
        if final_missing or final_changed:
            operation.status = OperationStatus.FAILED
            operation.error_summary = (
                "Pre-mutation Fresh Check Auto-Add не пройден: "
                f"missing={final_missing}; changed={final_changed}. Mutation blocked."
            )
            operation.completed_at = utc_now()
            self.repository.save_operation(operation)
            raise RuntimeError(operation.error_summary)

        operation.status = transition(operation.status, OperationStatus.RUNNING)
        self.repository.save_operation(operation)
        try:
            result = self.adapter.delete_auto_add_products(
                operation.action_id,
                auto_add_date=auto_add_date,
                product_ids=ids,
            )
        except Exception as exc:
            category = str(getattr(exc, "category", "UNKNOWN_RESULT"))
            operation.status = OperationStatus.VERIFICATION_FAILED if category == "UNKNOWN_RESULT" else OperationStatus.FAILED
            operation.error_summary = (
                "Auto-Add mutation outcome unknown; reconciliation required"
                if category == "UNKNOWN_RESULT" else str(exc)
            )
            operation.completed_at = utc_now()
            self.repository.save_operation(operation)
            raise

        acknowledged = set(result.deactivated_product_ids)
        rejected = {str(x.get("product_id")): str(x.get("reason") or x) for x in result.rejected}
        for item in operation.items:
            if item.product_id in rejected:
                item.error = rejected[item.product_id]
                item.status = ItemStatus.REJECTED
            elif item.product_id in acknowledged:
                item.status = ItemStatus.SUCCESS

        # Read-after-write reconciliation. Only reads may be retried.
        # The post-mutation state is the source of truth for a DELETE:
        # absent from Auto-Add => CONFIRMED_REMOVED; present => STILL_PRESENT.
        # A failed reconciliation read is UNKNOWN and MUST NOT trigger a retry.
        try:
            after_rows = self.adapter.list_auto_add_products(
                operation.action_id, auto_add_date=auto_add_date, limit=100
            )
            after_ids = {_pid(row) for row in after_rows}
            for item in operation.items:
                if item.product_id not in after_ids:
                    item.verification_result = "CONFIRMED_REMOVED"
                    item.status = ItemStatus.SUCCESS
                    # If Ozon's mutation response contradicted the observed state,
                    # retain the response as a warning but trust the read-after-write state.
                    if item.product_id in rejected:
                        item.warning = (
                            "Mutation response contained a rejection, but read-after-write "
                            "confirmed the product is absent from Auto-Add."
                        )
                else:
                    item.verification_result = "STILL_PRESENT"
                    item.status = ItemStatus.UNKNOWN_RESULT
                    item.warning = (
                        "Read-after-write: товар всё ещё присутствует в Auto-Add; "
                        "повторная mutation запрещена."
                    )
        except Exception as exc:
            for item in operation.items:
                item.verification_result = "UNKNOWN"
                item.status = ItemStatus.UNKNOWN_RESULT
                item.warning = (
                    "Не удалось выполнить read-after-write reconciliation; "
                    "повторная mutation запрещена до ручной проверки."
                )
            operation.status = OperationStatus.VERIFICATION_FAILED
            operation.error_summary = f"Auto-Add reconciliation UNKNOWN: {exc}"
            operation.completed_at = utc_now()
            self.repository.save_operation(operation)
            raise

        unresolved = [
            i.product_id for i in operation.items
            if i.verification_result in {"STILL_PRESENT", "UNKNOWN"}
        ]
        confirmed_removed = [
            i.product_id for i in operation.items
            if i.verification_result == "CONFIRMED_REMOVED"
        ]
        if unresolved:
            operation.status = (
                OperationStatus.PARTIAL
                if confirmed_removed else OperationStatus.VERIFICATION_FAILED
            )
            operation.error_summary = (
                f"Не подтверждено удаление: {unresolved}; "
                f"подтверждено удаление: {confirmed_removed}"
            )
        else:
            operation.status = OperationStatus.SUCCESS
        operation.completed_at = utc_now()
        self.repository.save_operation(operation)
        return operation, result


class AutoAddRollbackService:
    """Safe rollback for AUTO_ADD_DELETE snapshots.

    The source snapshot is the immutable target state. Rollback itself is a new
    mutation and therefore gets its own pre-mutation snapshot, confirmation,
    final Fresh Check and read-after-write reconciliation.
    """

    def __init__(self, adapter, repository):
        self.adapter = adapter
        self.repository = repository
        self.snapshot_service = SnapshotService(repository)

    def prepare(self, source_snapshot_id: str, user: str) -> Operation:
        rows = self.repository.get_snapshot(source_snapshot_id)
        if not rows:
            raise ValueError("Snapshot не найден")
        if any(str(r["membership"] or "") != "auto_add" for r in rows):
            raise ValueError("Snapshot не является Auto-Add DELETE snapshot")
        dates = {str(r["auto_add_date"] or "") for r in rows}
        if not dates or "" in dates or len(dates) != 1:
            raise ValueError("Snapshot не содержит однозначную auto_add_date; rollback заблокирован")
        auto_add_date = next(iter(dates))
        action_id = str(rows[0]["action_id"])
        targets = {str(r["product_id"]): r for r in rows}
        if any(not str(r["action_price"] or "").strip() for r in rows):
            raise ValueError("Snapshot не содержит исходных Auto-Add prices")

        current_rows = self.adapter.list_auto_add_products(action_id, auto_add_date=auto_add_date, limit=100)
        current = {_pid(row): row for row in current_rows}
        already_present = sorted(set(targets) & set(current))
        if already_present:
            raise ValueError(
                "Rollback заблокирован: товары уже присутствуют в Auto-Add: "
                + ", ".join(already_present)
            )

        op = OperationFactory.create(action_id, user, created_by="auto_add_rollback", operation_type="AUTO_ADD_ROLLBACK")
        op.source_snapshot_id = source_snapshot_id
        op.items = [OperationItem(
            operation_id=op.operation_id,
            product_id=pid,
            old_action_price=Decimal("0"),
            requested_action_price=Decimal(str(row["action_price"])),
        ) for pid, row in sorted(targets.items())]
        op.request_fingerprint = OperationFactory.fingerprint(
            action_id,
            [(auto_add_date + ":" + i.product_id, i.requested_action_price) for i in op.items],
            "AUTO_ADD_ROLLBACK",
        )
        op.status = transition(op.status, OperationStatus.PREVIEWED)
        op.error_summary = f"Auto-Add rollback preview; date={auto_add_date}"
        return op

    def execute(self, operation: Operation, user: str) -> tuple[Operation, MutationResult]:
        if operation.status != OperationStatus.PREVIEWED:
            raise ValueError("Auto-Add rollback requires Preview")
        source_rows = self.repository.get_snapshot(operation.source_snapshot_id) if operation.source_snapshot_id else []
        dates = {str(r["auto_add_date"] or "") for r in source_rows}
        if len(dates) != 1 or "" in dates:
            raise ValueError("Auto-Add rollback date is UNKNOWN")
        auto_add_date = next(iter(dates))

        # Fresh Check: all rollback targets must still be absent.
        fresh_rows = self.adapter.list_auto_add_products(operation.action_id, auto_add_date=auto_add_date, limit=100)
        fresh_ids = {_pid(row) for row in fresh_rows}
        present = [item.product_id for item in operation.items if item.product_id in fresh_ids]
        if present:
            operation.status = OperationStatus.FAILED
            operation.error_summary = f"Rollback Fresh Check failed: already present={present}"
            operation.completed_at = utc_now()
            self.repository.save_operation(operation)
            raise RuntimeError(operation.error_summary)

        operation.status = transition(operation.status, OperationStatus.FRESH_CHECKED)
        self.repository.save_operation(operation)

        # Snapshot the exact pre-rollback state: products are absent. The source
        # snapshot remains immutable and contains the prices to restore.
        snapshot_id = __import__("uuid").uuid4().hex
        self.repository.save_operation(operation)
        self.repository.save_auto_add_absent_snapshot(
            snapshot_id,
            operation.operation_id,
            operation.action_id,
            auto_add_date,
            [item.product_id for item in operation.items],
            action_prices={item.product_id: item.requested_action_price for item in operation.items},
        )
        operation.snapshot_id = snapshot_id
        operation.status = transition(operation.status, OperationStatus.SNAPSHOTTED)
        operation.confirmation_at = utc_now()
        operation.requested_by_user = user
        operation.status = transition(operation.status, OperationStatus.CONFIRMED)
        self.repository.save_operation(operation)

        # Final Fresh Check immediately before mutation. No retry if this fails.
        final_rows = self.adapter.list_auto_add_products(operation.action_id, auto_add_date=auto_add_date, limit=100)
        final_ids = {_pid(row) for row in final_rows}
        if any(item.product_id in final_ids for item in operation.items):
            operation.status = OperationStatus.FAILED
            operation.error_summary = "Pre-mutation Fresh Check failed: Auto-Add state changed"
            operation.completed_at = utc_now()
            self.repository.save_operation(operation)
            raise RuntimeError(operation.error_summary)

        operation.status = transition(operation.status, OperationStatus.RUNNING)
        self.repository.save_operation(operation)
        products = [{
            "product_id": item.product_id,
            "action_price": item.requested_action_price,
            "currency": "RUB",
        } for item in operation.items]
        try:
            result = self.adapter.update_auto_add_products(
                operation.action_id,
                auto_add_date=auto_add_date,
                products=products,
            )
        except Exception as exc:
            category = str(getattr(exc, "category", "UNKNOWN_RESULT"))
            operation.status = OperationStatus.VERIFICATION_FAILED if category == "UNKNOWN_RESULT" else OperationStatus.FAILED
            operation.error_summary = "Auto-Add rollback mutation outcome unknown; reconciliation required" if category == "UNKNOWN_RESULT" else str(exc)
            operation.completed_at = utc_now()
            self.repository.save_operation(operation)
            raise

        rejected = {str(x.get("product_id")): str(x.get("reason") or x) for x in result.rejected}
        warnings = {str(x.get("product_id")): str(x.get("message") or x.get("reason") or x) for x in result.warnings}
        for item in operation.items:
            if item.product_id in rejected:
                item.status = ItemStatus.REJECTED
                item.error = rejected[item.product_id]
            elif item.product_id in warnings:
                item.warning = warnings[item.product_id]

        # Read-after-write reconciliation is the source of truth.
        try:
            after_rows = self.adapter.list_auto_add_products(operation.action_id, auto_add_date=auto_add_date, limit=100)
            after = {_pid(row): row for row in after_rows}
            confirmed = 0
            unresolved = 0
            for item in operation.items:
                row = after.get(item.product_id)
                if row is None:
                    item.status = ItemStatus.UNKNOWN_RESULT
                    item.verification_result = "UNKNOWN_NOT_PRESENT"
                    item.warning = "Rollback response was accepted, but product is still absent from Auto-Add; retry запрещён."
                    unresolved += 1
                    continue
                actual = _money(row, "action_price_to_auto_add")
                item.actual_action_price = actual
                if actual == item.requested_action_price:
                    item.status = ItemStatus.SUCCESS
                    item.verification_result = "CONFIRMED_RESTORED"
                    confirmed += 1
                else:
                    item.status = ItemStatus.UNKNOWN_RESULT
                    item.verification_result = "RESTORED_PRICE_MISMATCH"
                    item.warning = f"Rollback restored product but price differs: actual={actual}, expected={item.requested_action_price}"
                    unresolved += 1
        except Exception as exc:
            for item in operation.items:
                item.status = ItemStatus.UNKNOWN_RESULT
                item.verification_result = "UNKNOWN"
                item.warning = "Не удалось выполнить rollback read-after-write; повторная mutation запрещена."
            operation.status = OperationStatus.VERIFICATION_FAILED
            operation.error_summary = f"Auto-Add rollback reconciliation UNKNOWN: {exc}"
            operation.completed_at = utc_now()
            self.repository.save_operation(operation)
            raise

        if unresolved:
            operation.status = OperationStatus.PARTIAL if confirmed else OperationStatus.VERIFICATION_FAILED
            operation.error_summary = f"Rollback reconciliation: confirmed={confirmed}; unresolved={unresolved}"
        else:
            operation.status = OperationStatus.SUCCESS
        operation.completed_at = utc_now()
        self.repository.save_operation(operation)
        return operation, result
