from decimal import Decimal
from pathlib import Path

import pytest

from app.adapters.mock import MockOzonAdapter
from app.domain.models import ItemStatus, OperationStatus, ProductState, Promotion
from app.domain.state_machine import transition
from app.repositories.sqlite import SQLiteRepository
from app.services.rollback import SafeRollbackService
from app.services.workflow import (
    FreshCheckService,
    MutationService,
    OperationFactory,
    ParticipantService,
    PreviewService,
    PromotionService,
    SnapshotService,
    VerificationService,
)


def products(action_id: str, n: int):
    return [
        ProductState(
            action_id, str(i), f"offer-{i}", f"P{i}", Decimal("1000"), Decimal("900"),
            Decimal("20"), Decimal("15"), Decimal("55"), Decimal("850"), Decimal("950"),
            "active", "available",
        )
        for i in range(1, n + 1)
    ]


def build_operation(tmp_path: Path, n: int):
    promotion = Promotion("1", "Эластичный бустинг", "active", metadata={"elastic": True})
    adapter = MockOzonAdapter([promotion], products("1", n))
    repo = SQLiteRepository(tmp_path / f"op-{n}.db")
    participant = ParticipantService(adapter)
    selected = participant.load("1")
    op = OperationFactory.create("1", "tester")
    PreviewService.build(op, selected, Decimal("880"))
    fresh = participant.current_state("1", {p.product_id for p in selected})
    assert not FreshCheckService.check(op, fresh, promotion)
    op.status = transition(op.status, OperationStatus.FRESH_CHECKED)
    SnapshotService(repo).create(op, fresh)
    MutationService(adapter, repo).confirm(op, "tester")
    return promotion, adapter, repo, op


def test_100_skus_real_batch_workflow(tmp_path):
    _, adapter, repo, op = build_operation(tmp_path, 100)
    MutationService(adapter, repo).execute(op)
    results = VerificationService(adapter, repo).verify(op)
    assert len(adapter.update_calls) == 1
    assert len(adapter.update_calls[0]) == 100
    assert len(results) == 100
    assert all(r.status == ItemStatus.SUCCESS for r in results)
    assert op.status == OperationStatus.SUCCESS


def test_101_skus_are_split_100_plus_1(tmp_path):
    _, adapter, repo, op = build_operation(tmp_path, 101)
    MutationService(adapter, repo).execute(op)
    results = VerificationService(adapter, repo).verify(op)
    assert [len(batch) for batch in adapter.update_calls] == [100, 1]
    assert len(results) == 101
    assert all(r.status == ItemStatus.SUCCESS for r in results)
    assert op.status == OperationStatus.SUCCESS


def test_warning_is_preserved_per_sku_and_is_not_failure(tmp_path):
    _, adapter, repo, op = build_operation(tmp_path, 3)
    adapter.warning_ids.add("2")
    MutationService(adapter, repo).execute(op)
    results = VerificationService(adapter, repo).verify(op)
    item = next(i for i in op.items if i.product_id == "2")
    result = next(r for r in results if r.product_id == "2")
    assert item.status == ItemStatus.WARNING
    assert item.warning == "mock warning"
    assert result.status == ItemStatus.WARNING
    assert result.warning == "mock warning"
    assert op.status == OperationStatus.SUCCESS
    persisted = repo.list_operation_items(op.operation_id)
    row = next(r for r in persisted if r["product_id"] == "2")
    assert row["warning"] == "mock warning"
    assert row["status"] == ItemStatus.WARNING.value


def test_rollback_uses_snapshot_action_id_not_current_ui_promotion(tmp_path):
    promotion_a = Promotion("A", "Эластичный бустинг A", "active", metadata={"elastic": True})
    promotion_b = Promotion("B", "Эластичный бустинг B", "inactive", metadata={"elastic": True})
    adapter = MockOzonAdapter([promotion_a, promotion_b], products("A", 2))
    repo = SQLiteRepository(tmp_path / "rollback-isolation.db")
    participant = ParticipantService(adapter)
    promotion_service = PromotionService(adapter)
    fresh_service = FreshCheckService()
    snapshot_service = SnapshotService(repo)
    mutation_service = MutationService(adapter, repo)
    verification_service = VerificationService(adapter, repo)

    op = OperationFactory.create("A", "tester")
    selected = participant.load("A")
    PreviewService.build(op, selected, Decimal("880"))
    fresh = participant.current_state("A", {p.product_id for p in selected})
    assert not fresh_service.check(op, fresh, promotion_a)
    op.status = transition(op.status, OperationStatus.FRESH_CHECKED)
    snapshot_service.create(op, fresh)
    mutation_service.confirm(op, "tester")
    mutation_service.execute(op)
    verification_service.verify(op)

    # Simulates the UI now selecting a different promotion. B is inactive, so
    # passing it into rollback would fail Fresh Check. The rollback service must
    # resolve A from the snapshot's action_id instead.
    rb = SafeRollbackService(
        repo, participant, PreviewService(), fresh_service, snapshot_service,
        mutation_service, verification_service, promotion_service,
    ).prepare(op.snapshot_id, "tester")
    assert rb.action_id == "A"
    assert rb.source_snapshot_id == op.snapshot_id
    assert rb.status == OperationStatus.SNAPSHOTTED


def test_fresh_check_failure_must_return_to_draft_via_state_machine(tmp_path):
    promotion = Promotion("1", "Эластичный бустинг", "active", metadata={"elastic": True})
    adapter = MockOzonAdapter([promotion], products("1", 1))
    repo = SQLiteRepository(tmp_path / "fresh-fail.db")
    selected = ParticipantService(adapter).load("1")
    op = OperationFactory.create("1", "tester")
    PreviewService.build(op, selected, Decimal("880"))
    changed = ProductState(**{**adapter.products["1"].__dict__, "action_price": Decimal("850")})
    fresh = {"1": changed}
    assert FreshCheckService.check(op, fresh, promotion)
    op.status = transition(op.status, OperationStatus.DRAFT)
    assert op.status == OperationStatus.DRAFT
    with pytest.raises(ValueError):
        transition(OperationStatus.DRAFT, OperationStatus.RUNNING)
