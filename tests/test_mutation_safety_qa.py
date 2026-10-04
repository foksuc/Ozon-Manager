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


def make_products(n=3):
    return [
        ProductState(
            "1", str(i), f"offer-{i}", f"P{i}", Decimal("1000"), Decimal("900"),
            Decimal("20"), Decimal("15"), Decimal("55"), Decimal("850"), Decimal("950"),
            "active", "available",
        )
        for i in range(1, n + 1)
    ]


def make_services(tmp_path: Path, n=3):
    promotion = Promotion("1", "Эластичный бустинг", "active", metadata={"elastic": True})
    adapter = MockOzonAdapter([promotion], make_products(n))
    repo = SQLiteRepository(tmp_path / "safety.db")
    participant = ParticipantService(adapter)
    preview = PreviewService()
    fresh = FreshCheckService()
    snapshot = SnapshotService(repo)
    mutation = MutationService(adapter, repo, batch_size=100)
    verify = VerificationService(adapter, repo)
    return promotion, adapter, repo, participant, preview, fresh, snapshot, mutation, verify


def prepared(tmp_path, n=3):
    promotion, adapter, repo, participant, preview, fresh, snapshot, mutation, verify = make_services(tmp_path, n)
    selected = participant.load("1")
    op = OperationFactory.create("1", "tester")
    preview.build(op, selected, Decimal("880"))
    current = participant.current_state("1", {p.product_id for p in selected})
    assert not fresh.check(op, current, promotion)
    op.status = transition(op.status, OperationStatus.FRESH_CHECKED)
    snapshot.create(op, current)
    return promotion, adapter, repo, participant, preview, fresh, snapshot, mutation, verify, op


def test_full_safety_sequence_persists_snapshot_and_history(tmp_path):
    *_, repo, participant, _, _, _, mutation, verify, op = prepared(tmp_path)
    row = repo.list_operations(limit=1)[0]
    assert row["snapshot_id"] == op.snapshot_id
    assert row["status"] == OperationStatus.SNAPSHOTTED.value

    mutation.confirm(op, "tester")
    assert op.status == OperationStatus.CONFIRMED
    mutation.execute(op)
    verify.verify(op)

    assert op.status == OperationStatus.SUCCESS
    history = repo.list_operations(limit=10)
    assert history[0]["operation_id"] == op.operation_id
    assert history[0]["status"] == OperationStatus.SUCCESS.value
    assert len(repo.get_snapshot(op.snapshot_id)) == 3


def test_mutation_without_preview_is_blocked(tmp_path):
    promotion, adapter, repo, participant, preview, fresh, snapshot, mutation, verify = make_services(tmp_path, 1)
    op = OperationFactory.create("1", "tester")
    with pytest.raises(ValueError):
        mutation.execute(op)
    assert adapter.update_calls == []


def test_mutation_without_snapshot_is_blocked(tmp_path):
    promotion, adapter, repo, participant, preview, fresh, snapshot, mutation, verify = make_services(tmp_path, 1)
    op = OperationFactory.create("1", "tester")
    selected = participant.load("1")
    preview.build(op, selected, Decimal("880"))
    op.status = transition(op.status, OperationStatus.FRESH_CHECKED)
    with pytest.raises(ValueError):
        mutation.confirm(op, "tester")
    assert adapter.update_calls == []


def test_stale_action_price_blocks_before_network_mutation(tmp_path):
    *_, adapter, _, participant, _, _, _, mutation, _, op = prepared(tmp_path, 1)
    adapter.products["1"] = ProductState(**{**adapter.products["1"].__dict__, "action_price": Decimal("850")})
    mutation.confirm(op, "tester")
    with pytest.raises(RuntimeError, match="Pre-mutation Fresh Check failed"):
        mutation.execute(op)
    assert adapter.update_calls == []
    assert op.status == OperationStatus.CONFIRMED


def test_stale_current_boost_blocks_before_network_mutation(tmp_path):
    *_, adapter, _, participant, _, _, _, mutation, _, op = prepared(tmp_path, 1)
    adapter.products["1"] = ProductState(**{**adapter.products["1"].__dict__, "current_boost": Decimal("21")})
    mutation.confirm(op, "tester")
    with pytest.raises(RuntimeError, match="current_boost изменился"):
        mutation.execute(op)
    assert adapter.update_calls == []


def test_unknown_mutation_result_is_fail_closed_and_cannot_be_blindly_retried(tmp_path):
    *_, adapter, repo, participant, _, _, _, mutation, _, op = prepared(tmp_path, 1)
    adapter.mutation_timeout = True
    mutation.confirm(op, "tester")
    with pytest.raises(RuntimeError):
        mutation.execute(op)
    assert op.status == OperationStatus.VERIFICATION_FAILED
    assert adapter.update_calls == []
    errors = repo.list_operations(limit=1)
    assert errors[0]["status"] == OperationStatus.VERIFICATION_FAILED.value
    with pytest.raises(ValueError):
        mutation.execute(op)
    assert adapter.update_calls == []


def test_mutation_requires_explicit_confirmation(tmp_path):
    *_, adapter, _, participant, _, _, _, mutation, _, op = prepared(tmp_path, 1)
    with pytest.raises(ValueError, match="explicit confirmation"):
        mutation.execute(op)
    assert adapter.update_calls == []


def test_promotion_inactive_blocks_pre_mutation_check(tmp_path):
    promotion, adapter, repo, participant, preview, fresh, snapshot, mutation, verify = make_services(tmp_path, 1)
    op = OperationFactory.create("1", "tester")
    selected = participant.load("1")
    preview.build(op, selected, Decimal("880"))
    current = participant.current_state("1", {"1"})
    op.status = transition(op.status, OperationStatus.FRESH_CHECKED)
    snapshot.create(op, current)
    adapter.promotions = [Promotion("1", promotion.title, "inactive", metadata={"elastic": True})]
    mutation.confirm(op, "tester")
    with pytest.raises(RuntimeError, match="Promotion недоступна"):
        mutation.execute(op)
    assert adapter.update_calls == []


def test_unknown_result_after_apply_is_fail_closed_and_not_retried(tmp_path):
    *_, adapter, repo, participant, _, _, _, mutation, _, op = prepared(tmp_path, 1)
    adapter.mutation_unknown_after_apply = True
    mutation.confirm(op, "tester")
    with pytest.raises(RuntimeError):
        mutation.execute(op)
    assert op.status == OperationStatus.VERIFICATION_FAILED
    assert adapter.products["1"].action_price == Decimal("880")
    assert adapter.update_calls == [["1"]]
    with pytest.raises(ValueError):
        mutation.execute(op)
    assert adapter.update_calls == [["1"]]


def test_partial_rejection_is_recorded_and_verified(tmp_path):
    *_, adapter, repo, participant, _, _, _, mutation, verify, op = prepared(tmp_path, 3)
    adapter.fail_ids.add("2")
    mutation.confirm(op, "tester")
    result = mutation.execute(op)
    assert result.rejected == ({"product_id": "2", "reason": "mock rejection"},)
    results = verify.verify(op)
    statuses = {r.product_id: r.status for r in results}
    assert statuses["1"] == ItemStatus.SUCCESS
    assert statuses["2"] == ItemStatus.REJECTED
    assert statuses["3"] == ItemStatus.SUCCESS
    assert op.status == OperationStatus.PARTIAL
    persisted = {r["product_id"]: r for r in repo.list_operation_items(op.operation_id)}
    assert persisted["2"]["status"] == ItemStatus.REJECTED.value
    assert persisted["2"]["error"] == "mock rejection"


def test_read_after_write_mismatch_is_verification_failure(tmp_path):
    *_, adapter, repo, participant, _, _, _, mutation, verify, op = prepared(tmp_path, 1)
    adapter.verify_mismatch_ids.add("1")
    mutation.confirm(op, "tester")
    mutation.execute(op)
    results = verify.verify(op)
    assert results[0].status == ItemStatus.VERIFICATION_FAILED
    assert op.status == OperationStatus.VERIFICATION_FAILED
    assert adapter.products["1"].action_price == Decimal("880")


def test_duplicate_fingerprint_blocks_second_mutation(tmp_path):
    *_, adapter, repo, participant, preview, fresh, snapshot, mutation, verify, op = prepared(tmp_path, 1)
    mutation.confirm(op, "tester")
    mutation.execute(op)
    verify.verify(op)

    op2 = OperationFactory.create("1", "tester")
    PreviewService.build(op2, participant.load("1"), Decimal("880"))
    current = participant.current_state("1", {"1"})
    op2.status = transition(op2.status, OperationStatus.FRESH_CHECKED)
    snapshot.create(op2, current)
    mutation.confirm(op2, "tester")
    with pytest.raises(ValueError, match="Duplicate operation fingerprint"):
        mutation.execute(op2)


def test_rollback_is_new_snapshot_backed_mutation(tmp_path):
    promotion, adapter, repo, participant, preview, fresh, snapshot, mutation, verify, op = prepared(tmp_path, 1)
    mutation.confirm(op, "tester")
    mutation.execute(op)
    verify.verify(op)
    assert adapter.products["1"].action_price == Decimal("880")

    rb = SafeRollbackService(
        repo, participant, preview, fresh, snapshot, mutation, verify,
        PromotionService(adapter),
    ).prepare(op.snapshot_id, "tester")
    assert rb.source_snapshot_id == op.snapshot_id
    assert rb.snapshot_id is not None
    assert rb.status == OperationStatus.SNAPSHOTTED
    assert rb.items[0].requested_action_price == Decimal("900")

    mutation.confirm(rb, "tester")
    mutation.execute(rb)
    verify.verify(rb)
    assert rb.status == OperationStatus.SUCCESS
    assert adapter.products["1"].action_price == Decimal("900")
    assert len(repo.get_snapshot(rb.snapshot_id)) == 1


def test_rollback_stale_price_blocks_before_second_mutation(tmp_path):
    promotion, adapter, repo, participant, preview, fresh, snapshot, mutation, verify, op = prepared(tmp_path, 1)
    mutation.confirm(op, "tester")
    mutation.execute(op)
    verify.verify(op)
    rb = SafeRollbackService(
        repo, participant, preview, fresh, snapshot, mutation, verify,
        PromotionService(adapter),
    ).prepare(op.snapshot_id, "tester")

    adapter.products["1"] = ProductState(**{**adapter.products["1"].__dict__, "action_price": Decimal("870")})
    mutation.confirm(rb, "tester")
    with pytest.raises(RuntimeError, match="Pre-mutation Fresh Check failed"):
        mutation.execute(rb)
    assert adapter.update_calls == [ ["1"] ]


def test_read_after_write_missing_is_unknown_result_not_not_found(tmp_path):
    *_, adapter, repo, participant, _, _, _, mutation, verify, op = prepared(tmp_path, 1)
    original = adapter.read_participants
    mutation.confirm(op, "tester")
    mutation.execute(op)
    adapter.read_participants = lambda action_id, **kwargs: []
    results = verify.verify(op)
    assert results[0].status == ItemStatus.UNKNOWN_RESULT
    assert op.status == OperationStatus.VERIFICATION_FAILED
    item = repo.list_operation_items(op.operation_id)[0]
    assert item["status"] == ItemStatus.UNKNOWN_RESULT.value
    assert "reconciliation" in (item["warning"] or "").lower()


def test_safe_rollback_add_is_remove_not_zero_price_activation(tmp_path):
    from app.adapters.mock import MockOzonAdapter
    from app.domain.models import Operation, OperationItem, OperationStatus, ProductState, Promotion, SnapshotItem, utc_now
    from app.repositories.sqlite import SQLiteRepository
    from app.services.rollback import SafeRollbackService
    from app.services.workflow import ParticipantService, SnapshotService

    product = ProductState("1", "100", "offer", "A", Decimal("1000"), Decimal("840"), Decimal("16"), Decimal("15"), Decimal("55"), Decimal("903.3"), Decimal("740"), "active", None)
    adapter = MockOzonAdapter([Promotion("1", "Elastic")], [product])
    repo = SQLiteRepository(tmp_path / "rollback.sqlite")
    source = Operation("source-add", "1", utc_now(), "test", "test", operation_type="ADD_PRODUCTS", status=OperationStatus.SUCCESS)
    source.items = [OperationItem("source-add", "100", Decimal("0"), Decimal("840"))]
    repo.save_operation(source)
    repo.save_snapshot("snap-add", "source-add", [SnapshotItem("1", "100", Decimal("1000"), Decimal("0"), Decimal("16"), Decimal("15"), Decimal("55"), Decimal("903.3"), Decimal("740"), "candidate", utc_now())])
    service = SafeRollbackService(repo, ParticipantService(adapter), None, None, SnapshotService(repo), type("M", (), {"adapter": adapter})(), None, None)
    plan = service.prepare("snap-add", "test")
    assert plan.operation_type == "ROLLBACK_ADD_REMOVE"
    assert plan.items[0].requested_action_price == Decimal("840")
    service.execute_membership_inverse(plan)
    assert adapter.read_participants("1") == []


def test_safe_rollback_remove_is_add_not_missing_participant(tmp_path):
    from app.adapters.mock import MockOzonAdapter
    from app.domain.models import Operation, OperationItem, OperationStatus, ProductState, Promotion, SnapshotItem, utc_now
    from app.repositories.sqlite import SQLiteRepository
    from app.services.rollback import SafeRollbackService
    from app.services.workflow import ParticipantService, SnapshotService

    product = ProductState("1", "200", "offer", "B", Decimal("1000"), Decimal("0"), Decimal("0"), Decimal("15"), Decimal("55"), Decimal("900"), Decimal("700"), "inactive", None)
    adapter = MockOzonAdapter([Promotion("1", "Elastic")], [product])
    repo = SQLiteRepository(tmp_path / "rollback.sqlite")
    source = Operation("source-remove", "1", utc_now(), "test", "test", operation_type="REMOVE_PRODUCTS", status=OperationStatus.SUCCESS)
    source.items = [OperationItem("source-remove", "200", Decimal("840"), Decimal("840"))]
    repo.save_operation(source)
    repo.save_snapshot("snap-remove", "source-remove", [SnapshotItem("1", "200", Decimal("1000"), Decimal("840"), Decimal("16"), Decimal("15"), Decimal("55"), Decimal("900"), Decimal("700"), "active", utc_now())])
    service = SafeRollbackService(repo, ParticipantService(adapter), None, None, SnapshotService(repo), type("M", (), {"adapter": adapter})(), None, None)
    plan = service.prepare("snap-remove", "test")
    assert plan.operation_type == "ROLLBACK_REMOVE_ADD"
    assert plan.items[0].requested_action_price == Decimal("840")
    service.execute_membership_inverse(plan)
    assert {p.product_id for p in adapter.read_participants("1")} == {"200"}
