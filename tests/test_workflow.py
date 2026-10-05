from decimal import Decimal
from pathlib import Path
import pytest

from app.adapters.mock import MockOzonAdapter
from app.domain.models import ProductState, Promotion, OperationStatus, ItemStatus
from app.repositories.sqlite import SQLiteRepository
from app.services.workflow import OperationFactory, PreviewService, FreshCheckService, SnapshotService, MutationService, VerificationService, ParticipantService, PromotionService, PromotionValidator, merge_product_catalog
from app.services.rollback import SafeRollbackService


def make_stack(tmp_path: Path):
    promotion = Promotion("1", "Эластичный бустинг", "active", metadata={"elastic": True})
    products = [ProductState("1", str(i), f"offer-{i}", f"P{i}", Decimal("1000"), Decimal("900"), Decimal("20"), Decimal("15"), Decimal("55"), Decimal("850"), Decimal("950"), "active", "available") for i in range(1, 4)]
    adapter = MockOzonAdapter([promotion], products)
    repo = SQLiteRepository(tmp_path / "test.db")
    return promotion, adapter, repo


def build_snapshot(tmp_path):
    promotion, adapter, repo = make_stack(tmp_path)
    participants = ParticipantService(adapter).load("1")
    op = OperationFactory.create("1", "tester")
    PreviewService.build(op, participants, Decimal("880"))
    fresh = ParticipantService(adapter).current_state("1", {p.product_id for p in participants})
    assert not FreshCheckService.check(op, fresh, promotion)
    op.status = OperationStatus.FRESH_CHECKED
    SnapshotService(repo).create(op, fresh)
    return promotion, adapter, repo, op


def test_preview_fresh_snapshot_mutation_verification(tmp_path):
    _, adapter, repo, op = build_snapshot(tmp_path)
    mutation = MutationService(adapter, repo)
    mutation.confirm(op, "tester")
    mutation.execute(op)
    results = VerificationService(adapter, repo).verify(op)
    assert op.status == OperationStatus.SUCCESS
    assert all(r.status == ItemStatus.SUCCESS for r in results)
    assert all(i.actual_action_price == Decimal("880") for i in op.items)


def test_fresh_check_blocks_changed_price(tmp_path):
    promotion, adapter, repo, op = build_snapshot(tmp_path)
    adapter.products["1"] = adapter.products["1"].__class__(**{**adapter.products["1"].__dict__, "action_price": Decimal("850")})
    fresh = ParticipantService(adapter).current_state("1", {i.product_id for i in op.items})
    errors = FreshCheckService.check(op, fresh, promotion)
    assert any("action_price" in e for e in errors)


def test_execute_blocks_if_price_changes_after_confirm(tmp_path):
    promotion, adapter, repo, op = build_snapshot(tmp_path)

    mutation = MutationService(adapter, repo)
    mutation.confirm(op, "tester")

    # Price changed after Confirm, but before mutation.
    adapter.products["1"] = adapter.products["1"].__class__(
        **{
            **adapter.products["1"].__dict__,
            "action_price": Decimal("850"),
        }
    )

    with pytest.raises(RuntimeError):
        mutation.execute(op)

    # Critical safety assertion: mutation was never sent.
    assert adapter.update_calls == []

def test_partial_rejection(tmp_path):
    _, adapter, repo, op = build_snapshot(tmp_path)
    adapter.fail_ids.add("2")
    mutation = MutationService(adapter, repo)
    mutation.confirm(op, "tester")
    mutation.execute(op)
    results = VerificationService(adapter, repo).verify(op)
    assert op.status == OperationStatus.PARTIAL
    assert any(i.product_id == "2" and i.status == ItemStatus.REJECTED for i in op.items)
    assert sum(r.status == ItemStatus.SUCCESS for r in results) == 2


def test_verification_mismatch(tmp_path):
    _, adapter, repo, op = build_snapshot(tmp_path)
    adapter.verify_mismatch_ids.add("1")
    mutation = MutationService(adapter, repo)
    mutation.confirm(op, "tester")
    mutation.execute(op)
    VerificationService(adapter, repo).verify(op)
    assert op.status == OperationStatus.PARTIAL
    assert any(i.status == ItemStatus.VERIFICATION_FAILED for i in op.items)


def test_timeout_does_not_blind_retry(tmp_path):
    _, adapter, repo, op = build_snapshot(tmp_path)
    adapter.mutation_timeout = True
    mutation = MutationService(adapter, repo)
    mutation.confirm(op, "tester")
    with pytest.raises(RuntimeError):
        mutation.execute(op)
    assert op.status == OperationStatus.VERIFICATION_FAILED
    # No second mutation is attempted by the service.
    
def test_pre_mutation_fresh_check_timeout_blocks_mutation(tmp_path):
    _, adapter, repo, op = build_snapshot(tmp_path)

    mutation = MutationService(adapter, repo)
    mutation.confirm(op, "tester")

    adapter.timeout = True

    with pytest.raises(RuntimeError):
        mutation.execute(op)

    assert adapter.update_calls == []

def test_snapshot_contains_rollback_fields(tmp_path):
    _, _, repo, op = build_snapshot(tmp_path)
    rows = repo.get_snapshot(op.snapshot_id)
    assert len(rows) == 3
    row = rows[0]
    for field in ["action_id", "product_id", "price", "action_price", "current_boost", "min_boost", "max_boost", "price_min_elastic", "price_max_elastic", "membership"]:
        assert field in row.keys()

def test_rollback_blocks_if_price_changes_after_prepare(tmp_path):
    promotion, adapter, repo, source_op = build_snapshot(tmp_path)

    rollback = SafeRollbackService(
        repo,
        ParticipantService(adapter),
        PreviewService(),
        FreshCheckService(),
        SnapshotService(repo),
        MutationService(adapter, repo),
        VerificationService(adapter, repo),
        PromotionService(adapter),
    )

    op = rollback.prepare(source_op.snapshot_id, "tester")

    mutation = MutationService(adapter, repo)
    mutation.confirm(op, "tester")

    product_id = op.items[0].product_id
    adapter.products[product_id] = adapter.products[product_id].__class__(
        **{
            **adapter.products[product_id].__dict__,
            "action_price": Decimal("850"),
        }
    )

    with pytest.raises(RuntimeError):
        mutation.execute(op)

    assert adapter.update_calls == []

def test_configured_batch_size_is_used(tmp_path):
    _, adapter, repo, op = build_snapshot(tmp_path)
    mutation = MutationService(adapter, repo, batch_size=2)
    mutation.confirm(op, "tester")
    mutation.execute(op)
    assert [len(batch) for batch in adapter.update_calls] == [2, 1]


def test_invalid_batch_size_is_rejected(tmp_path):
    _, adapter, repo, _ = build_snapshot(tmp_path)
    with pytest.raises(ValueError, match="batch_size"):
        MutationService(adapter, repo, batch_size=0)


def test_unsupported_mutation_is_not_classified_as_unknown_result(tmp_path):
    _, adapter, repo, op = build_snapshot(tmp_path)
    mutation = MutationService(adapter, repo)
    mutation.confirm(op, "tester")

    class UnsupportedAdapter(MockOzonAdapter):
        def update_products(self, action_id, products):
            exc = RuntimeError("mutation unsupported")
            exc.category = "UNSUPPORTED_OPERATION"
            raise exc

    mutation.adapter = UnsupportedAdapter(adapter.promotions, adapter.products.values())
    mutation.participant_service = ParticipantService(mutation.adapter)
    mutation.promotion_service = PromotionService(mutation.adapter)

    with pytest.raises(RuntimeError, match="mutation unsupported"):
        mutation.execute(op)

    assert op.status == OperationStatus.FAILED
    rows = repo.list_operations(limit=10)
    assert rows[0]["status"] == OperationStatus.FAILED.value


def test_pre_mutation_fresh_check_read_failure_is_persisted_and_blocks(tmp_path):
    _, adapter, repo, op = build_snapshot(tmp_path)
    mutation = MutationService(adapter, repo)
    mutation.confirm(op, "tester")
    adapter.timeout = True

    with pytest.raises(RuntimeError, match="could not be completed"):
        mutation.execute(op)

    assert adapter.update_calls == []
    errors = repo.connect().execute(
        "SELECT * FROM errors WHERE operation_id=? ORDER BY error_id DESC",
        (op.operation_id,),
    ).fetchall()
    assert errors
    assert errors[0]["error_class"] == "PRE_MUTATION_FRESH_CHECK_READ_FAILED"
    assert errors[0]["response_classification"] == "MUTATION_BLOCKED"


def test_elastic_validator_accepts_raw_metadata_title_when_model_title_differs():
    promotion = Promotion(
        "4253043",
        "Максимальный бустинг",
        "active",
        metadata={
            "title": "Эластичный бустинг. Без ограничения срока действия",
            "описание": "Эластичный бустинг",
        },
    )
    PromotionValidator.ensure_elastic_promotion(promotion)


def test_elastic_validator_accepts_mock_explicit_elastic_flag():
    promotion = Promotion("1", "Эластичный бустинг", "active", metadata={"elastic": True})
    PromotionValidator.ensure_elastic_promotion(promotion)


def test_elastic_validator_accepts_nested_raw_metadata_text():
    promotion = Promotion(
        "1",
        "Максимальный бустинг",
        "active",
        metadata={"details": {"description": "Эластичный бустинг"}},
    )
    PromotionValidator.ensure_elastic_promotion(promotion)


def test_elastic_validator_rejects_generic_boosting_without_elastic_evidence():
    promotion = Promotion("2", "Максимальный бустинг", "active", metadata={})
    with pytest.raises(ValueError, match="не идентифицирована"):
        PromotionValidator.ensure_elastic_promotion(promotion)


def test_elastic_validator_accepts_explicit_action_type():
    from app.domain.models import Promotion
    from app.services.workflow import PromotionValidator

    PromotionValidator.ensure_elastic_promotion(
        Promotion(action_id="1", title="Максимальный бустинг", metadata={"action_type": "ELASTIC_BOOSTING"})
    )


def test_merge_product_catalog_keeps_manually_added_participant():
    candidate = {"id": 101, "action_price": "100"}
    participant = ProductState("1", "101", "offer-101", "P101", Decimal("120"), Decimal("100"), Decimal("10"), Decimal("5"), Decimal("20"), Decimal("90"), Decimal("110"), None, None)
    other = ProductState("1", "202", "offer-202", "P202", Decimal("220"), Decimal("200"), Decimal("15"), Decimal("5"), Decimal("25"), Decimal("180"), Decimal("210"), None, None)
    rows = merge_product_catalog([candidate], [participant, other])
    assert [row["product_id"] for row in rows] == ["101", "202"]
    assert rows[0]["participation"] == "participant"
    assert rows[1]["participation"] == "participant"


def test_product_name_service_enriches_candidates_and_participants():
    from app.services.workflow import ProductNameService

    class Adapter:
        def resolve_product_names(self, product_ids):
            assert set(product_ids) == {"1", "2"}
            return {"1": "Товар один", "2": "Товар два"}

    candidate = {"id": 1, "price": {"amount": "100"}}
    participant = ProductState("100", "2", "offer-2", None, Decimal("100"), Decimal("90"), None, None, None, None, None, "active", "available")
    candidates, participants, names = ProductNameService(Adapter()).enrich([candidate], [participant])
    assert candidates[0]["name"] == "Товар один"
    assert participants[0].name == "Товар два"
    assert names == {"1": "Товар один", "2": "Товар два"}


def test_product_name_service_900_products_makes_one_resolution_call():
    from app.services.workflow import ProductNameService

    calls = []

    class Adapter:
        def resolve_product_names(self, product_ids):
            calls.append(list(product_ids))
            return {pid: f"Товар {pid}" for pid in product_ids}

    candidate_rows = [{"id": i} for i in range(900)]
    participants = []
    candidates, participants, names = ProductNameService(Adapter()).enrich(candidate_rows, participants)

    assert len(candidates) == 900
    assert len(names) == 900
    assert len(calls) == 1
    assert len(calls[0]) == 900
