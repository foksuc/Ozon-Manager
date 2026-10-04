from decimal import Decimal
from pathlib import Path
from app.adapters.mock import MockOzonAdapter
from app.domain.models import ProductState, Promotion, OperationStatus, ItemStatus
from app.repositories.sqlite import SQLiteRepository
from app.services.workflow import OperationFactory, PreviewService, FreshCheckService, SnapshotService, ParticipantService, MutationService, VerificationService
from app.services.rollback import SafeRollbackService


def make(n):
    promotion = Promotion("1", "Эластичный бустинг", "active", metadata={"elastic": True})
    products = [ProductState("1", str(i), None, f"P{i}", Decimal("1000"), Decimal("900"), Decimal("20"), Decimal("15"), Decimal("55"), Decimal("850"), Decimal("950"), "active", "available") for i in range(1,n+1)]
    return promotion, products


def test_1000_preview_without_real_mutation(tmp_path):
    promotion, products = make(1000)
    adapter=MockOzonAdapter([promotion], products)
    repo=SQLiteRepository(tmp_path/"bulk.db")
    selected=products[:1000]
    op=OperationFactory.create("1","tester")
    PreviewService.build(op, selected, Decimal("880"))
    assert len(op.items)==1000
    assert op.status == OperationStatus.PREVIEWED
    assert not repo.list_operations()


def test_rollback_uses_snapshot_action_price(tmp_path):
    promotion, products = make(2)
    adapter=MockOzonAdapter([promotion], products)
    repo=SQLiteRepository(tmp_path/"rollback.db")
    participant=ParticipantService(adapter)
    preview=PreviewService()
    fresh=FreshCheckService()
    snapshot=SnapshotService(repo)
    mutation=MutationService(adapter, repo)
    verify=VerificationService(adapter, repo)

    op=OperationFactory.create("1","tester")
    selected=participant.load("1")
    preview.build(op, selected, Decimal("880"))
    current=participant.current_state("1", {p.product_id for p in selected})
    assert not fresh.check(op,current,promotion)
    op.status=OperationStatus.FRESH_CHECKED
    snapshot.create(op,current)
    mutation.confirm(op,"tester")
    mutation.execute(op)
    verify.verify(op)
    assert op.status == OperationStatus.SUCCESS

    promotion_service=__import__("app.services.workflow", fromlist=["PromotionService"]).PromotionService(adapter)
    rb=SafeRollbackService(repo, participant, preview, fresh, snapshot, mutation, verify, promotion_service)
    rb_op=rb.prepare(op.snapshot_id,"tester")
    assert rb_op.items[0].requested_action_price == Decimal("900")
    assert rb_op.status == OperationStatus.SNAPSHOTTED
    mutation.confirm(rb_op,"tester")
    mutation.execute(rb_op)
    verify.verify(rb_op)
    assert rb_op.status == OperationStatus.SUCCESS
    assert all(p.action_price == Decimal("900") for p in participant.load("1"))


def test_900_sku_mock_stress_mutation_without_real_ozon(tmp_path):
    promotion, products = make(900)
    adapter = MockOzonAdapter([promotion], products)
    repo = SQLiteRepository(tmp_path / "stress-900.db")
    participant = ParticipantService(adapter)
    selected = participant.load("1")

    op = OperationFactory.create("1", "tester")
    PreviewService.build(op, selected, Decimal("880"))
    current = participant.current_state("1", {p.product_id for p in selected})
    assert not FreshCheckService.check(op, current, promotion)
    op.status = OperationStatus.FRESH_CHECKED
    SnapshotService(repo).create(op, current)

    mutation = MutationService(adapter, repo, batch_size=100)
    mutation.confirm(op, "tester")
    mutation.execute(op)

    results = VerificationService(adapter, repo).verify(op)

    assert len(op.items) == 900
    assert [len(batch) for batch in adapter.update_calls] == [100] * 9
    assert len(results) == 900
    assert all(result.status == ItemStatus.SUCCESS for result in results)
    assert op.status == OperationStatus.SUCCESS
