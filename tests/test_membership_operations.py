from decimal import Decimal

import pytest

from app.adapters.mock import MockOzonAdapter
from app.domain.models import ProductState, Promotion, OperationStatus, ItemStatus, MutationResult
from app.repositories.sqlite import SQLiteRepository
from app.services.membership import AddProductsService, RemoveProductsService


def products():
    return [
        ProductState("1", "1", None, "Candidate", Decimal("1000"), Decimal("0"), Decimal("10"), Decimal("5"), Decimal("20"), Decimal("850"), Decimal("700"), "inactive", "available"),
        ProductState("1", "2", None, "Participant", Decimal("1000"), Decimal("900"), Decimal("10"), Decimal("5"), Decimal("20"), Decimal("850"), Decimal("700"), "active", "available"),
    ]


def adapter(tmp_path):
    return MockOzonAdapter([Promotion("1", "Эластичный бустинг", "active", metadata={"elastic": True})], products()), SQLiteRepository(tmp_path / "history.db")


def test_add_candidate_with_action_price(tmp_path):
    a, repo = adapter(tmp_path)
    result = AddProductsService(a, repo).execute("1", ["1"], {"1": Decimal("790")}, {"1": {"id": "1"}}, "tester", confirmed=True)
    assert "Добавлено: 1" in result
    assert a.products["1"].membership == "active"
    assert a.products["1"].action_price == Decimal("790")
    rows = repo.list_operations()
    assert {row["operation_type"] for row in rows} == {"ADD_PRODUCTS"}
    assert all(row["snapshot_id"] for row in rows)


def test_add_candidate_blocks_price_above_price_min_elastic(tmp_path):
    a, repo = adapter(tmp_path)
    with pytest.raises(ValueError, match="диапазон Ozon Elastic Boosting"):
        AddProductsService(a, repo).execute(
            "1", ["1"], {"1": Decimal("900")}, {"1": {"id": "1"}}, "tester", confirmed=True
        )
    assert a.products["1"].membership == "inactive"


def test_add_candidate_blocks_price_below_price_max_elastic(tmp_path):
    a, repo = adapter(tmp_path)
    with pytest.raises(ValueError, match="диапазон Ozon Elastic Boosting"):
        AddProductsService(a, repo).execute(
            "1", ["1"], {"1": Decimal("650")}, {"1": {"id": "1"}}, "tester", confirmed=True
        )
    assert a.products["1"].membership == "inactive"


def test_remove_participant(tmp_path):
    a, repo = adapter(tmp_path)
    removed = RemoveProductsService(a, repo).execute("1", ["2"], "tester", confirmed=True)
    assert removed == ["2"]
    assert a.read_participants("1") == []
    row = repo.list_operations(limit=1)[0]
    assert row["operation_type"] == "REMOVE_PRODUCTS"
    assert row["status"] == OperationStatus.SUCCESS.value
    assert row["snapshot_id"]


def test_remove_blocks_if_state_changes_between_fresh_reads(tmp_path):
    a, repo = adapter(tmp_path)
    original = a.read_participants
    calls = {"n": 0}
    def changing_read(action_id, **kwargs):
        calls["n"] += 1
        result = original(action_id, **kwargs)
        if calls["n"] == 2:
            a.products["2"] = a.products["2"].__class__(**{**a.products["2"].__dict__, "action_price": Decimal("899")})
            result = original(action_id, **kwargs)
        return result
    a.read_participants = changing_read
    with pytest.raises(RuntimeError):
        RemoveProductsService(a, repo).execute("1", ["2"], "tester", confirmed=True)
    assert a.products["2"].membership == "active"


def test_add_blocks_when_candidate_price_or_elastic_bounds_changed(tmp_path):
    a, repo = adapter(tmp_path)
    expected = {"1": {
        "id": "1",
        "price": {"amount": "1000"},
        "price_min_elastic": {"amount": "850"},
        "price_max_elastic": {"amount": "950"},
        "min_boost": 5,
        "max_boost": 20,
        "current_boost": 10,
    }}
    a.products["1"] = a.products["1"].__class__(**{**a.products["1"].__dict__, "price": Decimal("990")})
    with pytest.raises(RuntimeError, match="price"):
        AddProductsService(a, repo).execute("1", ["1"], {"1": Decimal("790")}, expected, "tester", confirmed=True)


def test_update_blocks_when_elastic_bound_changed(tmp_path):
    a, repo = adapter(tmp_path)
    expected = {"2": a.products["2"]}
    a.products["2"] = a.products["2"].__class__(**{**a.products["2"].__dict__, "price_min_elastic": Decimal("840")})
    with pytest.raises(RuntimeError, match="price_min_elastic"):
        from app.services.membership import UpdateParticipantPricesService
        UpdateParticipantPricesService(a, repo).execute("1", ["2"], {"2": Decimal("890")}, expected, "tester", confirmed=True)


def test_add_missing_after_mutation_is_unknown_not_mismatch_and_can_be_reconciled(tmp_path):
    class DelayedVisibilityAdapter(MockOzonAdapter):
        def __init__(self, promotions, products):
            super().__init__(promotions, products)
            self.hide_after_activation = False
            self.hidden_ids = set()

        def activate_products(self, action_id, product_ids, prices=None, stocks=None):
            result = super().activate_products(action_id, product_ids, prices=prices, stocks=stocks)
            self.hide_after_activation = True
            self.hidden_ids = {str(pid) for pid in product_ids}
            return result

        def read_participants(self, action_id, **kwargs):
            rows = super().read_participants(action_id, **kwargs)
            if self.hide_after_activation:
                return [p for p in rows if p.product_id not in self.hidden_ids]
            return rows

    adapter_obj = DelayedVisibilityAdapter(
        [Promotion("1", "Эластичный бустинг", "active", metadata={"elastic": True})],
        products(),
    )
    repo = SQLiteRepository(tmp_path / "history.db")

    with pytest.raises(RuntimeError, match="Результат добавления не подтверждён"):
        AddProductsService(adapter_obj, repo).execute(
            "1", ["1"], {"1": Decimal("790")}, {"1": {"id": "1"}}, "tester", confirmed=True
        )

    row = repo.list_operations(limit=1)[0]
    assert row["status"] == OperationStatus.VERIFICATION_FAILED.value
    item = repo.list_operation_items(row["operation_id"])[0]
    assert item["status"] == "UNKNOWN_RESULT"
    assert item["actual_action_price"] is None
    assert "не подтверждён" in row["error_summary"]
    assert adapter_obj.products["1"].action_price == Decimal("790")

    adapter_obj.hide_after_activation = False
    from app.services.membership import AddOperationReconciliationService
    message = AddOperationReconciliationService(adapter_obj, repo).reconcile(row["operation_id"])
    assert "подтверждено 1" in message
    row2 = repo.list_operations(limit=1)[0]
    assert row2["status"] == OperationStatus.SUCCESS.value
    item2 = repo.list_operation_items(row["operation_id"])[0]
    assert item2["status"] == "SUCCESS"
    assert item2["actual_action_price"] == "790"


def test_add_reconciles_eventual_visibility_without_repeating_mutation(tmp_path, monkeypatch):
    monkeypatch.setenv("OZON_ADD_RECONCILIATION_READ_ATTEMPTS", "3")
    monkeypatch.setenv("OZON_ADD_RECONCILIATION_READ_DELAY_SECONDS", "0")

    class EventuallyVisibleAdapter(MockOzonAdapter):
        def __init__(self, promotions, products):
            super().__init__(promotions, products)
            self.read_calls = 0
            self.activate_calls = 0

        def activate_products(self, action_id, product_ids, prices=None, stocks=None):
            self.activate_calls += 1
            return super().activate_products(action_id, product_ids, prices=prices, stocks=stocks)

        def read_participants(self, action_id, **kwargs):
            self.read_calls += 1
            rows = super().read_participants(action_id, **kwargs)
            if self.read_calls < 3:
                return []
            return rows

    adapter_obj = EventuallyVisibleAdapter(
        [Promotion("1", "Эластичный бустинг", "active", metadata={"elastic": True})],
        products(),
    )
    repo = SQLiteRepository(tmp_path / "history.db")

    result = AddProductsService(adapter_obj, repo).execute(
        "1", ["1"], {"1": Decimal("790")}, {"1": {"id": "1"}}, "tester", confirmed=True
    )
    assert "Добавлено: 1" in result
    assert adapter_obj.activate_calls == 1
    assert adapter_obj.read_calls == 3
    row = repo.list_operations(limit=1)[0]
    assert row["status"] == OperationStatus.SUCCESS.value
    item = repo.list_operation_items(row["operation_id"])[0]
    assert item["status"] == "SUCCESS"
    assert item["actual_action_price"] == "790"


def test_reconciliation_accepts_ozon_whole_ruble_rounding_as_confirmed(tmp_path):
    from app.domain.models import Operation, OperationItem
    from app.services.membership import AddOperationReconciliationService

    adapter_obj, repo = adapter(tmp_path)
    # Ozon read-back observed in action 1977747: requested 885.60 -> actual 886.
    op = Operation(
        operation_id="rounding-op",
        action_id="1",
        created_at="2026-10-01T00:00:00+00:00",
        created_by="tester",
        requested_by_user="tester",
        operation_type="ADD_PRODUCTS",
        status=OperationStatus.VERIFICATION_FAILED,
        error_summary="old PRICE_MISMATCH",
    )
    op.items = [
        OperationItem(
            operation_id=op.operation_id,
            product_id="1",
            old_action_price=Decimal("0"),
            requested_action_price=Decimal("885.60"),
            actual_action_price=None,
            status=ItemStatus.VERIFICATION_FAILED,
            verification_result="PRICE_MISMATCH",
        )
    ]
    repo.save_operation(op)

    # Make the participant state match the observed Ozon read-back.
    adapter_obj.products["1"] = adapter_obj.products["1"].__class__(
        **{**adapter_obj.products["1"].__dict__, "membership": "active", "action_price": Decimal("886")}
    )

    message = AddOperationReconciliationService(adapter_obj, repo).reconcile(op.operation_id)

    assert message == "Reconciliation: подтверждено 1, отклонено 0."
    row = repo.list_operations(limit=1)[0]
    assert row["status"] == OperationStatus.SUCCESS.value
    item = repo.list_operation_items(op.operation_id)[0]
    assert item["status"] == "SUCCESS"
    assert item["verification_result"] == "SUCCESS_RECONCILED"
    assert item["actual_action_price"] == "886"
    assert item["error"] is None


def test_update_participant_accepts_price_inside_ozon_elastic_range(tmp_path):
    a, repo = adapter(tmp_path)
    expected = {"2": a.products["2"]}
    from app.services.membership import UpdateParticipantPricesService
    result = UpdateParticipantPricesService(a, repo).execute(
        "1", ["2"], {"2": Decimal("800")}, expected, "tester", confirmed=True
    )
    assert "успешно: 1" in result
    assert a.products["2"].action_price == Decimal("800")


def test_update_participant_blocks_price_outside_ozon_elastic_range(tmp_path):
    a, repo = adapter(tmp_path)
    expected = {"2": a.products["2"]}
    from app.services.membership import UpdateParticipantPricesService
    with pytest.raises(ValueError, match="актуальный диапазон Ozon Elastic Boosting"):
        UpdateParticipantPricesService(a, repo).execute(
            "1", ["2"], {"2": Decimal("900")}, expected, "tester", confirmed=True
        )


def test_update_participant_accepts_price_inside_ozon_elastic_range(tmp_path):
    a, repo = adapter(tmp_path)
    expected = {"2": a.products["2"]}
    from app.services.membership import UpdateParticipantPricesService
    result = UpdateParticipantPricesService(a, repo).execute(
        "1", ["2"], {"2": Decimal("800")}, expected, "tester", confirmed=True
    )
    assert "успешно: 1" in result
    assert a.products["2"].action_price == Decimal("800")


def test_update_participant_blocks_price_outside_ozon_elastic_range(tmp_path):
    a, repo = adapter(tmp_path)
    expected = {"2": a.products["2"]}
    from app.services.membership import UpdateParticipantPricesService
    with pytest.raises(ValueError, match="актуальный диапазон Ozon Elastic Boosting"):
        UpdateParticipantPricesService(a, repo).execute(
            "1", ["2"], {"2": Decimal("900")}, expected, "tester", confirmed=True
        )


def test_remove_requires_ozon_mutation_acknowledgement(tmp_path):
    a, repo = adapter(tmp_path)

    class RejectingRemoveAdapter(MockOzonAdapter):
        def deactivate_products(self, action_id, product_ids):
            return MutationResult(
                deactivated_product_ids=(),
                rejected=tuple({"product_id": str(pid), "reason": "live rejection"} for pid in product_ids),
                transport_status=200,
            )

    a = RejectingRemoveAdapter(a.promotions, list(a.products.values()))
    with pytest.raises(RuntimeError, match="отклонены Ozon"):
        RemoveProductsService(a, repo).execute("1", ["2"], "tester", confirmed=True)
    assert a.products["2"].membership == "active"
    row = repo.list_operations(limit=1)[0]
    assert row["status"] == OperationStatus.VERIFICATION_FAILED.value


def test_remove_requires_both_response_ack_and_read_after_write(tmp_path):
    a, repo = adapter(tmp_path)

    class AcknowledgedButStillPresentAdapter(MockOzonAdapter):
        def deactivate_products(self, action_id, product_ids):
            return MutationResult(deactivated_product_ids=tuple(map(str, product_ids)), transport_status=200)

    a = AcknowledgedButStillPresentAdapter(a.promotions, list(a.products.values()))
    with pytest.raises(RuntimeError, match="всё ещё участники"):
        RemoveProductsService(a, repo).execute("1", ["2"], "tester", confirmed=True)
    row = repo.list_operations(limit=1)[0]
    assert row["status"] == OperationStatus.VERIFICATION_FAILED.value
