from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import replace
from decimal import Decimal
from typing import Any

from app.domain.models import *
from app.domain.state_machine import transition
from app.domain.validation import parse_action_price, action_price_matches_requested
from app.services.batching import chunked
from app.config import Settings


class PromotionValidator:
    @staticmethod
    def _metadata_contains_elastic(value: object) -> bool:
        """Find explicit Elastic Boosting text anywhere in raw Ozon metadata."""
        if value is None:
            return False
        if isinstance(value, dict):
            return any(PromotionValidator._metadata_contains_elastic(v) for v in value.values())
        if isinstance(value, (list, tuple, set)):
            return any(PromotionValidator._metadata_contains_elastic(v) for v in value)
        text = str(value).lower()
        return "эластич" in text or "elastic" in text

    @staticmethod
    def ensure_elastic_promotion(promotion: Promotion) -> None:
        metadata = promotion.metadata or {}

        # The normalized title can differ from the raw Ozon response. The raw
        # response is therefore the source for identification. We accept only
        # explicit Elastic evidence; generic "boosting" is not sufficient.
        explicit_action_type = str(metadata.get("action_type") or "").upper() == "ELASTIC_BOOSTING"
        explicit_elastic_flag = metadata.get("elastic") is True
        explicit_elastic_text = PromotionValidator._metadata_contains_elastic(metadata)
        explicit_model_text = PromotionValidator._metadata_contains_elastic(promotion.title)

        if not (explicit_action_type or explicit_elastic_flag or explicit_elastic_text or explicit_model_text):
            raise ValueError(
                "Выбранная рекламная акция не идентифицирована "
                "как Elastic Boosting по доступным метаданным"
            )


class PromotionService:
    def __init__(self, adapter):
        self.adapter = adapter

    def list_promotions(self):
        return self.adapter.list_promotions()

    def get_promotion(self, action_id: str):
        for p in self.list_promotions():
            if p.action_id == str(action_id):
                PromotionValidator.ensure_elastic_promotion(p)
                return p
        raise ValueError(f"Promotion {action_id} not found")


class ParticipantService:
    def __init__(self, adapter):
        self.adapter = adapter

    def load(self, action_id: str):
        return self.adapter.list_participants(action_id)

    def current_state(self, action_id: str, product_ids: set[str]):
        rows = self.adapter.read_participants(action_id)
        return {p.product_id: p for p in rows if p.product_id in product_ids}


class CandidateService:
    def __init__(self, adapter):
        self.adapter = adapter

    def load(self, action_id: str):
        return self.adapter.list_all_candidates(action_id)


class ProductNameService:
    """Read-only product-card name enrichment. Never participates in mutation."""

    def __init__(self, adapter):
        self.adapter = adapter

    def enrich(self, candidate_rows: list[dict], participants: list[ProductState]):
        ids = set()
        for row in candidate_rows:
            raw_id = row.get("id")
            if raw_id in (None, ""):
                raw_id = row.get("product_id")
            if raw_id not in (None, ""):
                ids.add(str(raw_id))
        ids.update(str(product.product_id) for product in participants)
        if not ids:
            return candidate_rows, participants, {}

        names = self.adapter.resolve_product_names(ids)
        enriched_candidates = []
        for row in candidate_rows:
            copy = dict(row)
            raw_id = copy.get("id")
            if raw_id in (None, ""):
                raw_id = copy.get("product_id")
            pid = str(raw_id) if raw_id not in (None, "") else ""
            if not copy.get("name") and names.get(pid):
                copy["name"] = names[pid]
            enriched_candidates.append(copy)

        enriched_participants = [
            replace(product, name=names.get(str(product.product_id), product.name))
            for product in participants
        ]
        return enriched_candidates, enriched_participants, names


def merge_product_catalog(candidate_rows: list[dict], participants: list[ProductState]) -> list[dict]:
    """Return the union of candidates and participants without hiding added SKUs."""
    participant_ids = {str(p.product_id) for p in participants}
    candidate_ids = {str(row.get("id", row.get("product_id", ""))) for row in candidate_rows}
    catalog: list[dict] = []

    for row in candidate_rows:
        product_id = str(row.get("id", row.get("product_id", "")))
        catalog.append({
            **row,
            "product_id": product_id,
            "participation": "participant" if product_id in participant_ids else "candidate",
        })

    for product in participants:
        product_id = str(product.product_id)
        if product_id in candidate_ids:
            continue
        catalog.append({
            "id": product_id,
            "product_id": product_id,
            "offer_id": product.offer_id,
            "name": product.name,
            "price": str(product.price) if product.price is not None else "",
            "action_price": str(product.action_price),
            "current_boost": str(product.current_boost) if product.current_boost is not None else "",
            "price_min_elastic": str(product.price_min_elastic) if product.price_min_elastic is not None else "",
            "price_max_elastic": str(product.price_max_elastic) if product.price_max_elastic is not None else "",
            "min_boost": str(product.min_boost) if product.min_boost is not None else "",
            "max_boost": str(product.max_boost) if product.max_boost is not None else "",
            "participation": "participant",
        })
    return catalog


class PreviewService:
    @staticmethod
    def build(operation: Operation, products: list[ProductState], requested_action_price: Decimal) -> Operation:
        if not products:
            raise ValueError("Не выбраны SKU")
        requested_action_price = parse_action_price(requested_action_price)
        operation.items = [OperationItem(
            operation_id=operation.operation_id,
            product_id=p.product_id,
            old_action_price=p.action_price,
            requested_action_price=requested_action_price,
            old_current_boost=p.current_boost,
        ) for p in products]
        operation.request_fingerprint = OperationFactory.fingerprint(
            operation.action_id, [(i.product_id, i.requested_action_price) for i in operation.items]
        )
        operation.status = transition(operation.status, OperationStatus.PREVIEWED)
        return operation


class FreshCheckService:
    SAFETY_FIELDS = ("action_price", "current_boost", "membership", "availability")

    @staticmethod
    def check(operation: Operation, fresh: dict[str, ProductState], promotion: Promotion) -> list[str]:
        errors = []
        if promotion.state and promotion.state.lower() in {"inactive", "disabled", "archived"}:
            errors.append("Promotion недоступна")
        for item in operation.items:
            p = fresh.get(item.product_id)
            if p is None:
                errors.append(f"SKU {item.product_id}: не найден при Fresh Check")
                continue
            if p.action_price != item.old_action_price:
                errors.append(f"SKU {item.product_id}: action_price изменился после Preview")
            if p.current_boost != item.old_current_boost:
                errors.append(f"SKU {item.product_id}: current_boost изменился после Preview")
            # Current v2 participant schema does not expose a membership field.
            # Presence in the participant list is the membership proof; if a
            # legacy/adapter-specific membership value is available, validate it.
            if p.membership is not None and str(p.membership).lower() in {"removed", "inactive", "not_member"}:
                errors.append(f"SKU {item.product_id}: membership недействителен")
            if p.availability is not None and str(p.availability).lower() in {"unavailable", "removed"}:
                errors.append(f"SKU {item.product_id}: товар недоступен")
        return errors


class SnapshotService:
    def __init__(self, repository):
        self.repository = repository

    def create(self, operation: Operation, fresh: dict[str, ProductState], *, auto_add_date: str | None = None) -> str:
        snapshot_id = uuid.uuid4().hex
        rows = []
        for item in operation.items:
            p = fresh[item.product_id]
            rows.append(SnapshotItem(
                action_id=p.action_id, product_id=p.product_id, price=p.price,
                action_price=p.action_price, current_boost=p.current_boost,
                min_boost=p.min_boost, max_boost=p.max_boost,
                price_min_elastic=p.price_min_elastic, price_max_elastic=p.price_max_elastic,
                membership=p.membership, timestamp=utc_now(), auto_add_date=auto_add_date, present=True))
        # Persist the operation first because snapshots reference it via FK.
        # Then persist the final snapshot linkage/status as a second durable
        # write. This prevents a crash between snapshot creation and
        # confirmation from leaving an orphaned, unlinked snapshot in history.
        self.repository.save_operation(operation)
        self.repository.save_snapshot(snapshot_id, operation.operation_id, rows)
        operation.snapshot_id = snapshot_id
        operation.status = transition(operation.status, OperationStatus.SNAPSHOTTED)
        self.repository.save_operation(operation)
        return snapshot_id


class MutationService:
    def __init__(self, adapter, repository, *, batch_size: int | None = None):
        self.adapter = adapter
        self.repository = repository
        self.batch_size = Settings().batch_size if batch_size is None else batch_size
        if self.batch_size < 1:
            raise ValueError("batch_size must be >= 1")
        self.participant_service = ParticipantService(adapter)
        self.promotion_service = PromotionService(adapter)
        self.fresh_check_service = FreshCheckService()

    def confirm(self, operation: Operation, user: str) -> None:
        if operation.status != OperationStatus.SNAPSHOTTED or not operation.snapshot_id:
            raise ValueError("Mutation requires Fresh Check and Snapshot")
        operation.confirmation_at = utc_now()
        operation.requested_by_user = user
        operation.status = transition(operation.status, OperationStatus.CONFIRMED)
        self.repository.save_operation(operation)

    def execute(self, operation: Operation) -> MutationResult:
        if operation.status != OperationStatus.CONFIRMED:
            raise ValueError("Mutation requires explicit confirmation")
        if operation.request_fingerprint and self.repository.has_fingerprint(operation.request_fingerprint):
            rows = self.repository.list_operations(limit=1000)
            duplicates = [r for r in rows if r["request_fingerprint"] == operation.request_fingerprint and r["operation_id"] != operation.operation_id and r["status"] not in {OperationStatus.CANCELLED.value}]
            if duplicates:
                raise ValueError("Duplicate operation fingerprint; mutation blocked")

        # Mandatory pre-mutation Fresh Check.
        # The operation remains CONFIRMED if the live state is stale.
        product_ids = {item.product_id for item in operation.items}
        try:
            promotion = self.promotion_service.get_promotion(operation.action_id)
            fresh = self.participant_service.current_state(
                operation.action_id,
                product_ids,
            )
        except Exception as exc:
            category = str(getattr(exc, "category", ErrorCategory.UNKNOWN_RESULT.value))
            status_code = getattr(exc, "status_code", None)
            self.repository.record_error(
                operation.operation_id,
                "PRE_MUTATION_FRESH_CHECK_READ_FAILED",
                str(exc),
                http_status=status_code,
                response_classification="MUTATION_BLOCKED",
                retryable=False,
                details={"category": category},
            )
            operation.error_summary = "Pre-mutation Fresh Check could not be completed; mutation blocked"
            self.repository.save_operation(operation)
            raise RuntimeError(operation.error_summary) from exc

        fresh_errors = self.fresh_check_service.check(
            operation,
            fresh,
            promotion,
        )

        if fresh_errors:
            message = "Pre-mutation Fresh Check failed: " + "; ".join(fresh_errors)
            self.repository.record_error(
                operation.operation_id,
                "PRE_MUTATION_FRESH_CHECK_FAILED",
                message,
                response_classification="MUTATION_BLOCKED",
                retryable=False,
                details={"errors": fresh_errors},
            )
            operation.error_summary = message
            self.repository.save_operation(operation)
            raise RuntimeError(message)

        operation.status = transition(operation.status, OperationStatus.RUNNING)
        self.repository.save_operation(operation)

        aggregate_active: list[str] = []
        aggregate_deactivated: list[str] = []
        aggregate_rejected: list[dict[str, Any]] = []
        aggregate_warnings: list[dict[str, Any]] = []
        transport_status: int | None = None

        for batch in chunked(operation.items, self.batch_size):
            payload = [{
                "product_id": i.product_id,
                "action_price": i.requested_action_price,
            } for i in batch]
            try:
                result = self.adapter.update_products(operation.action_id, payload)
            except Exception as exc:
                category = str(getattr(exc, "category", ErrorCategory.UNKNOWN_RESULT.value))
                status_code = getattr(exc, "status_code", None)
                unknown_result = category == ErrorCategory.UNKNOWN_RESULT.value
                if category not in {member.value for member in ErrorCategory}:
                    category = ErrorCategory.UNKNOWN_RESULT.value
                    unknown_result = True

                self.repository.record_error(
                    operation.operation_id,
                    category,
                    str(exc),
                    http_status=status_code,
                    response_classification="UNKNOWN_RESULT" if unknown_result else (
                        "MUTATION_BLOCKED" if category == ErrorCategory.UNSUPPORTED_OPERATION.value else "API_ERROR"
                    ),
                    retryable=False,
                )
                operation.status = transition(
                    operation.status,
                    OperationStatus.VERIFICATION_FAILED if unknown_result else OperationStatus.FAILED,
                )
                operation.error_summary = (
                    "Mutation outcome unknown; reconciliation required"
                    if unknown_result
                    else str(exc)
                )
                operation.completed_at = utc_now()
                self.repository.save_operation(operation)
                raise

            aggregate_active.extend(result.active_product_ids)
            aggregate_deactivated.extend(result.deactivated_product_ids)
            aggregate_rejected.extend(result.rejected)
            aggregate_warnings.extend(result.warnings)
            if result.transport_status is not None:
                if transport_status is None:
                    transport_status = result.transport_status
                elif transport_status != result.transport_status:
                    transport_status = None

        rejected_by_id = {
            str(r.get("product_id")): str(r.get("reason") or r.get("message") or r)
            for r in aggregate_rejected if r.get("product_id") is not None
        }
        warnings_by_id: dict[str, list[str]] = {}
        for warning in aggregate_warnings:
            pid = warning.get("product_id")
            if pid is not None:
                warnings_by_id.setdefault(str(pid), []).append(
                    str(warning.get("message") or warning.get("reason") or warning)
                )

        for item in operation.items:
            if item.product_id in rejected_by_id:
                item.status = ItemStatus.REJECTED
                item.error = rejected_by_id[item.product_id]
            elif item.product_id in warnings_by_id:
                item.status = ItemStatus.WARNING
                item.warning = "; ".join(warnings_by_id[item.product_id])

        self.repository.save_operation(operation)
        return MutationResult(
            active_product_ids=tuple(aggregate_active),
            deactivated_product_ids=tuple(aggregate_deactivated),
            rejected=tuple(aggregate_rejected),
            warnings=tuple(aggregate_warnings),
            transport_status=transport_status,
        )


class VerificationService:
    def __init__(self, adapter, repository):
        self.adapter = adapter
        self.repository = repository

    def verify(self, operation: Operation) -> list[VerificationResult]:
        actual = {p.product_id: p for p in self.adapter.read_participants(operation.action_id)}
        results = []
        for item in operation.items:
            if item.status == ItemStatus.REJECTED:
                results.append(VerificationResult(item.product_id, ItemStatus.REJECTED, item.requested_action_price, None, item.old_current_boost, None, error=item.error))
                continue
            p = actual.get(item.product_id)
            if p is None:
                # A post-write read that cannot find the product is ambiguous:
                # it may be eventual consistency, pagination, or an incomplete
                # read. It is not evidence that the mutation failed.
                item.status = ItemStatus.UNKNOWN_RESULT
                item.verification_result = "UNKNOWN_RESULT"
                item.warning = "Read-after-write не подтвердил состояние; повторная mutation запрещена без reconciliation."
                results.append(VerificationResult(item.product_id, ItemStatus.UNKNOWN_RESULT, item.requested_action_price, None, item.old_current_boost, None, warning=item.warning))
                continue
            item.actual_action_price = p.action_price
            item.new_current_boost = p.current_boost
            if not action_price_matches_requested(item.requested_action_price, p.action_price):
                item.status = ItemStatus.VERIFICATION_FAILED
                item.verification_result = "PRICE_CHANGED"
                results.append(VerificationResult(item.product_id, ItemStatus.VERIFICATION_FAILED, item.requested_action_price, p.action_price, item.old_current_boost, p.current_boost, error="Actual action_price differs from requested"))
                continue
            if p.current_boost != item.old_current_boost:
                item.status = ItemStatus.BOOST_CHANGED
                item.verification_result = "BOOST_CHANGED"
                results.append(VerificationResult(item.product_id, ItemStatus.SUCCESS, item.requested_action_price, p.action_price, item.old_current_boost, p.current_boost, warning="current_boost changed; price mutation verified"))
                continue
            if item.warning:
                item.status = ItemStatus.WARNING
                item.verification_result = "SUCCESS_WITH_WARNING"
                results.append(VerificationResult(item.product_id, ItemStatus.WARNING, item.requested_action_price, p.action_price, item.old_current_boost, p.current_boost, warning=item.warning))
                continue
            item.status = ItemStatus.SUCCESS
            item.verification_result = "SUCCESS"
            results.append(VerificationResult(item.product_id, ItemStatus.SUCCESS, item.requested_action_price, p.action_price, item.old_current_boost, p.current_boost))
        statuses = [r.status for r in results]
        successful = {ItemStatus.SUCCESS, ItemStatus.WARNING}
        if statuses and all(s in successful for s in statuses):
            operation.status = transition(operation.status, OperationStatus.SUCCESS)
        elif statuses and any(s in successful for s in statuses):
            operation.status = transition(operation.status, OperationStatus.PARTIAL)
        elif any(s in {ItemStatus.VERIFICATION_FAILED, ItemStatus.NOT_FOUND, ItemStatus.UNKNOWN_RESULT} for s in statuses):
            operation.status = transition(operation.status, OperationStatus.VERIFICATION_FAILED)
        else:
            operation.status = transition(operation.status, OperationStatus.FAILED)
        operation.completed_at = utc_now()
        self.repository.save_operation(operation)
        return results


class HistoryService:
    def __init__(self, repository):
        self.repository = repository

    def persist(self, operation: Operation):
        self.repository.save_operation(operation)


class RollbackService:
    def __init__(self, repository, participant_service, preview_service, fresh_service, snapshot_service, mutation_service, verification_service):
        self.repository = repository
        self.participant_service = participant_service
        self.preview_service = preview_service
        self.fresh_service = fresh_service
        self.snapshot_service = snapshot_service
        self.mutation_service = mutation_service
        self.verification_service = verification_service

    def load_targets(self, snapshot_id: str):
        return self.repository.get_snapshot(snapshot_id)


class OperationFactory:
    @staticmethod
    def create(action_id: str, user: str, created_by: str = "streamlit", operation_type: str = "UPDATE_PRICE") -> Operation:
        return Operation(operation_id=uuid.uuid4().hex, action_id=str(action_id), created_at=utc_now(), created_by=created_by, requested_by_user=user, operation_type=operation_type)

    @staticmethod
    def fingerprint(action_id: str, items: list[tuple[str, Decimal]], operation_type: str = "UPDATE_PRICE") -> str:
        canonical = json.dumps({"action_id": str(action_id), "operation_type": str(operation_type), "items": sorted((str(pid), str(price)) for pid, price in items)}, separators=(",", ":"))
        return hashlib.sha256(canonical.encode()).hexdigest()
