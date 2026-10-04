from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Any


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class OperationStatus(str, Enum):
    DRAFT = "DRAFT"
    PREVIEWED = "PREVIEWED"
    FRESH_CHECKED = "FRESH_CHECKED"
    SNAPSHOTTED = "SNAPSHOTTED"
    CONFIRMED = "CONFIRMED"
    RUNNING = "RUNNING"
    PARTIAL = "PARTIAL"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    VERIFICATION_FAILED = "VERIFICATION_FAILED"
    CANCELLED = "CANCELLED"


class ItemStatus(str, Enum):
    PENDING = "PENDING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    REJECTED = "REJECTED"
    WARNING = "WARNING"
    VERIFICATION_FAILED = "VERIFICATION_FAILED"
    PRICE_CHANGED = "PRICE_CHANGED"
    NOT_FOUND = "NOT_FOUND"
    UNKNOWN_RESULT = "UNKNOWN_RESULT"
    BOOST_CHANGED = "BOOST_CHANGED"


class ErrorCategory(str, Enum):
    AUTH_ERROR = "AUTH_ERROR"
    API_ERROR = "API_ERROR"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    PROMOTION_ERROR = "PROMOTION_ERROR"
    PRODUCT_ERROR = "PRODUCT_ERROR"
    MUTATION_ERROR = "MUTATION_ERROR"
    PARTIAL_RESULT = "PARTIAL_RESULT"
    FRESH_CHECK_FAILED = "FRESH_CHECK_FAILED"
    VERIFICATION_FAILED = "VERIFICATION_FAILED"
    UNKNOWN_RESULT = "UNKNOWN_RESULT"
    UNSUPPORTED_OPERATION = "UNSUPPORTED_OPERATION"
    DATABASE_ERROR = "DATABASE_ERROR"


@dataclass(frozen=True)
class Promotion:
    action_id: str
    title: str
    state: str | None = None
    start_at: str | None = None
    end_at: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ProductState:
    action_id: str
    product_id: str
    offer_id: str | None
    name: str | None
    price: Decimal | None
    action_price: Decimal
    current_boost: Decimal | None
    min_boost: Decimal | None
    max_boost: Decimal | None
    price_min_elastic: Decimal | None
    price_max_elastic: Decimal | None
    membership: str | None
    availability: str | None
    currency: str = "RUB"
    max_action_price: Decimal | None = None


@dataclass(frozen=True)
class PreviewItem:
    product: ProductState
    requested_action_price: Decimal
    delta: Decimal
    warnings: tuple[str, ...] = ()
    validation_error: str | None = None


@dataclass(frozen=True)
class SnapshotItem:
    action_id: str
    product_id: str
    price: Decimal | None
    action_price: Decimal
    current_boost: Decimal | None
    min_boost: Decimal | None
    max_boost: Decimal | None
    price_min_elastic: Decimal | None
    price_max_elastic: Decimal | None
    membership: str | None
    timestamp: str
    auto_add_date: str | None = None
    present: bool = True


@dataclass
class OperationItem:
    operation_id: str
    product_id: str
    old_action_price: Decimal
    requested_action_price: Decimal
    actual_action_price: Decimal | None = None
    old_current_boost: Decimal | None = None
    new_current_boost: Decimal | None = None
    status: ItemStatus = ItemStatus.PENDING
    error: str | None = None
    warning: str | None = None
    verification_result: str | None = None


@dataclass
class Operation:
    operation_id: str
    action_id: str
    created_at: str
    created_by: str
    requested_by_user: str
    operation_type: str = "UPDATE_PRICE"
    status: OperationStatus = OperationStatus.DRAFT
    confirmation_at: str | None = None
    completed_at: str | None = None
    error_summary: str | None = None
    correlation_id: str | None = None
    request_fingerprint: str | None = None
    snapshot_id: str | None = None
    source_snapshot_id: str | None = None
    items: list[OperationItem] = field(default_factory=list)


@dataclass(frozen=True)
class MutationResult:
    active_product_ids: tuple[str, ...] = ()
    deactivated_product_ids: tuple[str, ...] = ()
    rejected: tuple[dict[str, Any], ...] = ()
    warnings: tuple[dict[str, Any], ...] = ()
    transport_status: int | None = None


@dataclass(frozen=True)
class VerificationResult:
    product_id: str
    status: ItemStatus
    expected_action_price: Decimal
    actual_action_price: Decimal | None
    before_current_boost: Decimal | None
    after_current_boost: Decimal | None
    warning: str | None = None
    error: str | None = None
