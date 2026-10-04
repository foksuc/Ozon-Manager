from __future__ import annotations

from decimal import Decimal
from typing import Any
import time
import os

from app.domain.models import ItemStatus, Operation, OperationItem, OperationStatus, ProductState, utc_now
from app.domain.state_machine import transition
from app.domain.validation import action_price_matches_requested
from app.services.workflow import FreshCheckService, MutationService, OperationFactory, SnapshotService, VerificationService
from app.services.price_engine import calculate_candidate_elastic_price


def _money(value: Any, default: Decimal = Decimal("0")) -> Decimal:
    if isinstance(value, dict):
        value = value.get("amount")
    if value in (None, ""):
        return default
    return Decimal(str(value))


def candidate_to_product(action_id: str, row: dict[str, Any]) -> ProductState:
    pid = row.get("id", row.get("product_id"))
    return ProductState(
        action_id=str(action_id),
        product_id=str(pid),
        offer_id=str(row["offer_id"]) if row.get("offer_id") is not None else None,
        name=row.get("name"),
        price=_money(row.get("price"), None),
        action_price=_money(row.get("action_price")),
        current_boost=_money(row.get("current_boost"), None),
        min_boost=_money(row.get("min_boost"), None),
        max_boost=_money(row.get("max_boost"), None),
        price_min_elastic=_money(row.get("price_min_elastic"), None),
        price_max_elastic=_money(row.get("price_max_elastic"), None),
        membership=row.get("membership") or row.get("status"),
        availability=row.get("availability"),
        currency="RUB",
    )




def _row_money(row: dict[str, Any], key: str) -> Decimal | None:
    value = row.get(key)
    if isinstance(value, dict):
        value = value.get("amount")
    if value in (None, ""):
        return None
    try:
        return Decimal(str(value))
    except Exception:
        return None


def _candidate_safety_diffs(expected: dict[str, Any], actual: dict[str, Any]) -> list[str]:
    fields = ("price", "price_min_elastic", "price_max_elastic", "min_boost", "max_boost", "current_boost")
    diffs = []
    for field in fields:
        # Partial candidate fixtures/responses may omit optional fields.
        # Missing on the expected side is UNKNOWN, not evidence of a change.
        if field not in expected:
            continue
        if _row_money(expected, field) != _row_money(actual, field):
            diffs.append(field)
    return diffs

def _participant_safety_diffs(expected: ProductState, actual: ProductState) -> list[str]:
    fields = ("price", "price_min_elastic", "price_max_elastic", "min_boost", "max_boost", "current_boost")
    return [field for field in fields if getattr(expected, field) != getattr(actual, field)]


def _set_items(operation: Operation, products: list[ProductState], prices: dict[str, Decimal]) -> None:
    operation.items = [
        OperationItem(
            operation_id=operation.operation_id,
            product_id=p.product_id,
            old_action_price=p.action_price,
            requested_action_price=prices.get(p.product_id, p.action_price),
            old_current_boost=p.current_boost,
        )
        for p in products
    ]
    operation.request_fingerprint = OperationFactory.fingerprint(
        operation.action_id,
        [(i.product_id, i.requested_action_price) for i in operation.items],
        operation.operation_type,
    )
    operation.status = transition(operation.status, OperationStatus.PREVIEWED)


class AddProductsService:
    """Safe candidate -> participant flow.

    The activation contract carries action_price. For a new participant, ADD
    therefore performs one protected activation mutation and verifies the
    resulting action_price; UPDATE for an existing participant uses the same
    Ozon activate endpoint through UpdateParticipantPricesService.
    """

    def __init__(self, adapter, repository):
        self.adapter = adapter
        self.repository = repository
        self.snapshot_service = SnapshotService(repository)
        self.mutation_service = MutationService(adapter, repository)
        self.verification_service = VerificationService(adapter, repository)

    def execute(self, action_id: str, product_ids: list[str], prices: dict[str, Decimal], candidate_rows: dict[str, dict], user: str, *, confirmed: bool = False) -> str:
        if not confirmed:
            raise ValueError("ADD mutation requires explicit confirmation")
        selected = [str(pid) for pid in product_ids]
        if not selected:
            raise ValueError("Не выбраны товары для добавления")
        current_candidates = {str(r.get("id", r.get("product_id"))): r for r in self.adapter.list_all_candidates(action_id)}
        current_participants = {p.product_id: p for p in self.adapter.read_participants(action_id)}
        missing = [pid for pid in selected if pid not in current_candidates]
        already = [pid for pid in selected if pid in current_participants]
        changed = []
        for pid in selected:
            expected = candidate_rows.get(pid) if candidate_rows else None
            actual = current_candidates.get(pid)
            if expected is not None and actual is not None:
                diffs = _candidate_safety_diffs(expected, actual)
                if diffs:
                    changed.append(f"{pid}: {', '.join(diffs)}")
        if missing or already or changed:
            raise RuntimeError(
                "Fresh Check добавления не пройден: "
                f"missing_candidates={missing}; already_participants={already}; changed={changed}. "
                "Требуется обновить данные и пересчитать."
            )

        products = [candidate_to_product(action_id, current_candidates[pid]) for pid in selected]
        # Fail closed before snapshot/mutation: ADD must land inside the
        # per-product Elastic Boosting price interval returned by Ozon.
        invalid_prices = []
        for product in products:
            try:
                calculate_candidate_elastic_price(
                    product.price,
                    (product.price - Decimal(str(prices[product.product_id]))) / product.price * Decimal("100"),
                    product.price_min_elastic,
                    product.price_max_elastic,
                )
            except Exception as exc:
                invalid_prices.append(f"{product.product_id}: {exc}")
        if invalid_prices:
            raise ValueError("ADD заблокирован: цена не попадает в диапазон Ozon Elastic Boosting. " + "; ".join(invalid_prices))

        op = OperationFactory.create(action_id, user, operation_type="ADD_PRODUCTS")
        _set_items(op, products, {pid: prices[pid] for pid in selected})
        op.status = transition(op.status, OperationStatus.FRESH_CHECKED)
        self.snapshot_service.create(op, {p.product_id: p for p in products})
        self.mutation_service.confirm(op, user)
        # Fresh Check immediately before the activation mutation.
        latest_candidates = {str(r.get("id", r.get("product_id"))): r for r in self.adapter.list_all_candidates(action_id)}
        latest_participants = {p.product_id for p in self.adapter.read_participants(action_id)}
        stale = []
        for pid in selected:
            latest = latest_candidates.get(pid)
            baseline = products[[p.product_id for p in products].index(pid)]
            if latest is None or pid in latest_participants:
                stale.append(pid)
                continue
            latest_product = candidate_to_product(action_id, latest)
            diffs = _participant_safety_diffs(baseline, latest_product)
            if diffs:
                stale.append(f"{pid}: {', '.join(diffs)}")
        if stale:
            op.status = OperationStatus.FAILED
            op.error_summary = f"Pre-mutation Fresh Check failed before add: {stale}. Требуется refresh/recalculate."
            self.repository.save_operation(op)
            raise RuntimeError(op.error_summary)
        op.status = transition(op.status, OperationStatus.RUNNING)
        self.repository.save_operation(op)
        try:
            result = self.adapter.activate_products(action_id, selected, prices=prices)
        except Exception as exc:
            category = str(getattr(exc, "category", "UNKNOWN_RESULT"))
            op.status = OperationStatus.VERIFICATION_FAILED if category == "UNKNOWN_RESULT" else OperationStatus.FAILED
            op.error_summary = "Add mutation outcome unknown; reconciliation required" if category == "UNKNOWN_RESULT" else str(exc)
            op.completed_at = utc_now()
            self.repository.save_operation(op)
            raise

        rejected = {
            str(r.get("product_id")): str(r.get("reason") or r.get("message") or r)
            for r in result.rejected
            if r.get("product_id") is not None
        }
        active_ack = {str(pid) for pid in result.active_product_ids}
        for item in op.items:
            if item.product_id in rejected:
                item.status = ItemStatus.REJECTED
                item.error = rejected[item.product_id]
            elif item.product_id in active_ack:
                item.warning = "Ozon activate подтвердил товар; ожидается подтверждение через read-after-write."

        # The mutation response is not a substitute for read-after-write.
        # Ozon membership reads may become visible after the mutation response,
        # therefore the application performs bounded READ-ONLY reconciliation.
        # IMPORTANT: only READ is retried; activate/mutation is never retried.
        # The policy is application-level and configurable, not an Ozon API limit.
        read_attempts = max(1, int(os.getenv("OZON_ADD_RECONCILIATION_READ_ATTEMPTS", "3")))
        read_delay = max(0.0, float(os.getenv("OZON_ADD_RECONCILIATION_READ_DELAY_SECONDS", "1.0")))
        pending_ids = {item.product_id for item in op.items if item.status != ItemStatus.REJECTED}
        after = {}
        for attempt in range(read_attempts):
            participants = self.adapter.read_participants(action_id)
            after = {p.product_id: p for p in participants}
            pending_ids -= set(after)
            if not pending_ids:
                break
            if attempt + 1 < read_attempts and read_delay:
                time.sleep(read_delay)

        unknown = []
        mismatched = []
        for item in op.items:
            if item.status == ItemStatus.REJECTED:
                continue
            p = after.get(item.product_id)
            if p is None:
                item.status = ItemStatus.UNKNOWN_RESULT
                item.verification_result = "UNKNOWN_RESULT"
                item.warning = (item.warning + " " if item.warning else "") + "Read-after-write не подтвердил участие товара; повторная mutation запрещена без reconciliation."
                unknown.append(item.product_id)
                continue
            item.actual_action_price = p.action_price
            item.new_current_boost = p.current_boost
            if not action_price_matches_requested(item.requested_action_price, p.action_price):
                item.status = ItemStatus.VERIFICATION_FAILED
                item.verification_result = "PRICE_MISMATCH"
                item.error = f"actual_action_price={p.action_price}; requested={item.requested_action_price}"
                mismatched.append(item.product_id)
            elif item.status != ItemStatus.WARNING:
                item.status = ItemStatus.SUCCESS
                item.verification_result = "SUCCESS"
            else:
                item.verification_result = "SUCCESS_WITH_WARNING"

        op.completed_at = utc_now()
        if unknown:
            op.status = OperationStatus.VERIFICATION_FAILED
            op.error_summary = (
                "Результат добавления не подтверждён read-after-write для: "
                f"{unknown}. Повторная mutation не выполнялась; требуется reconciliation."
            )
            self.repository.record_error(
                op.operation_id, "UNKNOWN_RESULT", op.error_summary,
                response_classification="UNKNOWN_RESULT", retryable=False,
                details={"product_ids": unknown},
            )
        elif mismatched:
            op.status = OperationStatus.VERIFICATION_FAILED
            op.error_summary = f"После добавления action_price не совпадает с requested: {mismatched}"
            self.repository.record_error(
                op.operation_id, "VERIFICATION_FAILED", op.error_summary,
                response_classification="PRICE_MISMATCH", retryable=False,
                details={"product_ids": mismatched},
            )
        elif rejected:
            op.status = OperationStatus.PARTIAL if len(rejected) < len(selected) else OperationStatus.FAILED
            op.error_summary = None
        else:
            op.status = OperationStatus.SUCCESS
            op.error_summary = None
        self.repository.save_operation(op)
        if unknown or mismatched:
            raise RuntimeError(op.error_summary)
        return f"Добавлено: {len(selected) - len(rejected)}; отклонено: {len(rejected)}"


class UpdateParticipantPricesService:
    def __init__(self, adapter, repository):
        self.adapter = adapter
        self.repository = repository
        self.snapshot_service = SnapshotService(repository)
        self.mutation_service = MutationService(adapter, repository)
        self.verification_service = VerificationService(adapter, repository)

    def execute(self, action_id: str, product_ids: list[str], prices: dict[str, Decimal], expected_products: dict[str, ProductState], user: str, *, confirmed: bool = False) -> str:
        if not confirmed:
            raise ValueError("Price mutation requires explicit confirmation")
        live = {p.product_id: p for p in self.adapter.read_participants(action_id)}
        missing = [pid for pid in product_ids if pid not in live]
        changed = []
        for pid in product_ids:
            if pid not in live or pid not in expected_products:
                continue
            expected = expected_products[pid]
            actual = live[pid]
            diffs = []
            if actual.action_price != expected.action_price:
                diffs.append("action_price")
            diffs.extend(_participant_safety_diffs(expected, actual))
            if diffs:
                changed.append(f"{pid}: {', '.join(dict.fromkeys(diffs))}")
        if missing or changed:
            raise RuntimeError(f"Fresh Check цены не пройден: missing={missing}; changed={changed}. Требуется обновить таблицу и пересчитать.")
        products = [live[pid] for pid in product_ids]
        invalid_prices = []
        for product in products:
            try:
                requested = Decimal(str(prices[product.product_id]))
                discount = (product.price - requested) / product.price * Decimal("100")
                calculate_candidate_elastic_price(
                    product.price,
                    discount,
                    product.price_min_elastic,
                    product.price_max_elastic,
                )
            except Exception as exc:
                invalid_prices.append(f"{product.product_id}: {exc}")
        if invalid_prices:
            raise ValueError(
                "UPDATE_PRICE заблокирован: новая цена не попадает в актуальный диапазон Ozon Elastic Boosting. "
                + "; ".join(invalid_prices)
            )
        op = OperationFactory.create(action_id, user, operation_type="UPDATE_PRICE")
        _set_items(op, products, prices)
        op.status = transition(op.status, OperationStatus.FRESH_CHECKED)
        self.snapshot_service.create(op, {p.product_id: p for p in products})
        self.mutation_service.confirm(op, user)
        self.mutation_service.execute(op)
        self.verification_service.verify(op)
        self.repository.save_operation(op)
        if op.status == OperationStatus.VERIFICATION_FAILED:
            raise RuntimeError("Проверка после изменения цены не пройдена")
        successful = sum(1 for item in op.items if item.status in {ItemStatus.SUCCESS, ItemStatus.WARNING})
        rejected = sum(1 for item in op.items if item.status == ItemStatus.REJECTED)
        failed = len(op.items) - successful - rejected
        return f"Результат: {op.status.value}; успешно: {successful}; отклонено: {rejected}; ошибки проверки: {failed}"


class RemoveProductsService:
    def __init__(self, adapter, repository):
        self.adapter = adapter
        self.repository = repository
        self.snapshot_service = SnapshotService(repository)

    def execute(self, action_id: str, product_ids: list[str], user: str, *, confirmed: bool = False) -> list[str]:
        if not confirmed:
            raise ValueError("REMOVE mutation requires explicit confirmation")
        selected = [str(pid) for pid in product_ids]
        live = {p.product_id: p for p in self.adapter.read_participants(action_id)}
        missing = [pid for pid in selected if pid not in live]
        if missing:
            raise RuntimeError(f"Fresh Check удаления не пройден: товары уже отсутствуют в акции: {missing}")
        products = [live[pid] for pid in selected]
        op = OperationFactory.create(action_id, user, operation_type="REMOVE_PRODUCTS")
        _set_items(op, products, {pid: live[pid].action_price for pid in selected})
        op.status = transition(op.status, OperationStatus.FRESH_CHECKED)
        self.snapshot_service.create(op, {p.product_id: p for p in products})
        op.confirmation_at = utc_now()
        op.status = transition(op.status, OperationStatus.CONFIRMED)
        # Fresh Check immediately before the deactivation mutation.
        latest = {p.product_id: p for p in self.adapter.read_participants(action_id)}
        stale = [
            pid for pid in selected
            if pid not in latest
            or latest[pid].action_price != live[pid].action_price
            or latest[pid].current_boost != live[pid].current_boost
        ]
        if stale:
            op.status = OperationStatus.FAILED
            op.error_summary = f"Pre-mutation Fresh Check failed before remove: {stale}"
            self.repository.save_operation(op)
            raise RuntimeError(op.error_summary)
        op.status = transition(op.status, OperationStatus.RUNNING)
        self.repository.save_operation(op)
        try:
            mutation_result = self.adapter.deactivate_products(action_id, selected)
        except Exception as exc:
            category = str(getattr(exc, "category", "UNKNOWN_RESULT"))
            op.status = OperationStatus.VERIFICATION_FAILED if category == "UNKNOWN_RESULT" else OperationStatus.FAILED
            op.error_summary = "Remove mutation outcome unknown; reconciliation required" if category == "UNKNOWN_RESULT" else str(exc)
            op.completed_at = utc_now()
            self.repository.save_operation(op)
            raise
        # Ozon returns per-product mutation outcomes. An explicit rejection is
        # stronger evidence than HTTP 200 and must never be hidden by a
        # subsequent read. Likewise, an accepted response is not sufficient
        # on its own: read-after-write remains mandatory.
        acknowledged = {str(pid) for pid in (mutation_result.deactivated_product_ids or ())}
        rejected_ids = {str(item.get("product_id")) for item in (mutation_result.rejected or ()) if isinstance(item, dict) and item.get("product_id") is not None}
        missing_from_response = [pid for pid in selected if pid not in acknowledged]
        after = {p.product_id for p in self.adapter.read_participants(action_id)}
        still_present = [pid for pid in selected if pid in after]
        if rejected_ids or missing_from_response or still_present:
            details = []
            if rejected_ids:
                details.append(f"отклонены Ozon: {sorted(rejected_ids)}")
            if missing_from_response:
                details.append(f"не подтверждены ответом Ozon: {missing_from_response}")
            if still_present:
                details.append(f"всё ещё участники: {still_present}")
            op.status = OperationStatus.VERIFICATION_FAILED
            op.error_summary = "Удаление не подтверждено: " + "; ".join(details)
            op.completed_at = utc_now()
            self.repository.save_operation(op)
            raise RuntimeError(op.error_summary)
        for item in op.items:
            item.status = ItemStatus.SUCCESS
        op.status = OperationStatus.SUCCESS
        op.completed_at = utc_now()
        self.repository.save_operation(op)
        return selected


class AddOperationReconciliationService:
    """Reconcile an ADD mutation whose post-write state was not confirmed.

    This service performs read-only reconciliation only. It never re-sends the
    mutation, which prevents blind retries after an ambiguous Ozon outcome.
    """

    def __init__(self, adapter, repository):
        self.adapter = adapter
        self.repository = repository

    def reconcile(self, operation_id: str) -> str:
        row = self.repository.get_operation(operation_id)
        if row is None:
            raise ValueError(f"Операция не найдена: {operation_id}")
        if row["operation_type"] != "ADD_PRODUCTS":
            raise ValueError("Reconciliation поддерживает только ADD_PRODUCTS")
        if row["status"] != OperationStatus.VERIFICATION_FAILED.value:
            raise ValueError("Reconciliation доступен только для операций с неподтверждённым результатом")

        items = self.repository.list_operation_items(operation_id)
        selected = [str(r["product_id"]) for r in items]
        read_attempts = max(1, int(os.getenv("OZON_ADD_RECONCILIATION_READ_ATTEMPTS", "3")))
        read_delay = max(0.0, float(os.getenv("OZON_ADD_RECONCILIATION_READ_DELAY_SECONDS", "1.0")))
        actual = {}
        pending_ids = {str(r["product_id"]) for r in items if r["status"] != ItemStatus.REJECTED.value}
        for attempt in range(read_attempts):
            actual = {p.product_id: p for p in self.adapter.read_participants(str(row["action_id"]))}
            pending_ids -= set(actual)
            if not pending_ids:
                break
            if attempt + 1 < read_attempts and read_delay:
                time.sleep(read_delay)
        unknown = []
        mismatch = []
        success = 0
        rejected_count = 0
        from app.domain.models import Operation, OperationItem
        op = Operation(
            operation_id=row["operation_id"], action_id=row["action_id"], created_at=row["created_at"],
            created_by=row["created_by"], requested_by_user=row["requested_by_user"],
            operation_type=row["operation_type"], status=OperationStatus(row["status"]),
            confirmation_at=row["confirmation_at"], completed_at=row["completed_at"],
            error_summary=row["error_summary"], correlation_id=row["correlation_id"],
            request_fingerprint=row["request_fingerprint"], snapshot_id=row["snapshot_id"],
            source_snapshot_id=row["source_snapshot_id"],
        )
        for r in items:
            item = OperationItem(
                operation_id=operation_id, product_id=str(r["product_id"]),
                old_action_price=Decimal(str(r["old_action_price"])),
                requested_action_price=Decimal(str(r["requested_action_price"])),
                actual_action_price=Decimal(str(r["actual_action_price"])) if r["actual_action_price"] is not None else None,
                old_current_boost=Decimal(str(r["old_current_boost"])) if r["old_current_boost"] is not None else None,
                new_current_boost=Decimal(str(r["new_current_boost"])) if r["new_current_boost"] is not None else None,
                status=ItemStatus(r["status"]), error=r["error"], warning=r["warning"], verification_result=r["verification_result"],
            )
            if item.status == ItemStatus.REJECTED:
                rejected_count += 1
            else:
                p = actual.get(item.product_id)
                if p is None:
                    item.status = ItemStatus.UNKNOWN_RESULT
                    item.verification_result = "UNKNOWN_RESULT"
                    item.warning = "Read-after-write всё ещё не подтверждает участие; mutation не повторялась."
                    unknown.append(item.product_id)
                else:
                    item.actual_action_price = p.action_price
                    item.new_current_boost = p.current_boost
                    if not action_price_matches_requested(item.requested_action_price, p.action_price):
                        item.status = ItemStatus.VERIFICATION_FAILED
                        item.verification_result = "PRICE_MISMATCH"
                        item.error = f"actual_action_price={p.action_price}; requested={item.requested_action_price}"
                        mismatch.append(item.product_id)
                    else:
                        item.status = ItemStatus.SUCCESS
                        item.error = None
                        item.verification_result = "SUCCESS_RECONCILED"
                        success += 1
            op.items.append(item)

        if unknown:
            op.status = OperationStatus.VERIFICATION_FAILED
            op.error_summary = f"Reconciliation не подтвердил результат для: {unknown}"
            self.repository.record_error(
                operation_id, "UNKNOWN_RESULT", op.error_summary,
                response_classification="RECONCILIATION_INCOMPLETE", retryable=False,
                details={"product_ids": unknown},
            )
        elif mismatch:
            op.status = OperationStatus.VERIFICATION_FAILED
            op.error_summary = f"После reconciliation action_price не совпадает с requested: {mismatch}"
            self.repository.record_error(
                operation_id, "VERIFICATION_FAILED", op.error_summary,
                response_classification="PRICE_MISMATCH", retryable=False,
                details={"product_ids": mismatch},
            )
        elif rejected_count and success:
            op.status = OperationStatus.PARTIAL
            op.error_summary = None
        elif rejected_count and not success:
            op.status = OperationStatus.FAILED
            op.error_summary = None
        else:
            op.status = OperationStatus.SUCCESS
            op.error_summary = None
        op.completed_at = utc_now()
        self.repository.save_operation(op)
        if unknown:
            return f"Reconciliation: подтверждено {success}, неизвестно {len(unknown)}, отклонено {rejected_count}. Mutation не повторялась."
        if mismatch:
            return f"Reconciliation: подтверждено {success}, mismatch {len(mismatch)}, отклонено {rejected_count}. Mutation не повторялась."
        return f"Reconciliation: подтверждено {success}, отклонено {rejected_count}."
