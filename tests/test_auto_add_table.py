import pytest

from decimal import Decimal

from app.adapters.ozon import OzonCredentials, OzonPromotionsAdapter
from app.services.read_cache import ReadDataCache
from app.ui.display import calculate_auto_add_discount_percent, format_auto_add_rows


def test_format_auto_add_rows_preserves_api_values():
    rows = format_auto_add_rows([{
        "product_id": 123,
        "sku": 456,
        "offer_id": "OFFER",
        "name": "Товар",
        "price": 1800,
        "max_discount_price": 1648,
        "min_seller_price": 1476,
        "marketplace_seller_price": 1500,
        "action_price_to_auto_add": 1833,
        "min_action_quantity": 0,
        "quantity_to_auto_add": 1,
        "currency": "RUB",
        "add_mode": "AUTO",
    }])
    assert rows[0]["Идентификатор товара"] == "123"
    assert rows[0]["Название"] == "Товар"
    assert rows[0]["Цена"] == "1800"
    assert rows[0]["Максимальная цена со скидкой"] == "1648"
    assert rows[0]["Цена автодобавления"] == "1833"
    assert rows[0]["Режим"] == "AUTO"


def test_auto_add_discount_is_calculated_from_price_and_action_price():
    discount = calculate_auto_add_discount_percent({
        "price": 1800,
        "action_price_to_auto_add": 1500,
    })
    assert discount is not None
    assert discount.quantize(Decimal("0.01")) == Decimal("16.67")


def test_auto_add_discount_preserves_negative_value_when_action_price_is_higher():
    discount = calculate_auto_add_discount_percent({
        "price": 1800,
        "action_price_to_auto_add": 1833,
    })
    assert discount is not None
    assert discount < 0
    assert discount.quantize(Decimal("0.01")) == Decimal("-1.83")


def test_auto_add_formatter_exposes_calculated_discount_column():
    rows = format_auto_add_rows([{
        "product_id": 123,
        "price": 1800,
        "action_price_to_auto_add": 1500,
    }])
    assert rows[0]["Скидка"] == "16.67%"


def test_auto_add_cache_round_trip():
    cache = ReadDataCache()
    rows = [{"product_id": 1, "name": "A"}]
    cache.mark_auto_add("1977747", "2026-10-08T21:00:00Z", rows)
    assert cache.has_auto_add_data("1977747")
    assert cache.auto_add_date == "2026-10-08T21:00:00Z"
    assert cache.auto_add_rows == rows


def test_auto_add_adapter_uses_exact_date_and_paginates(monkeypatch):
    adapter = OzonPromotionsAdapter(
        OzonCredentials("cid", "key"), "https://example.invalid", 10
    )
    calls = []

    responses = [
        {"products": [{"product_id": 1}], "total": 2},
        {"products": [{"product_id": 2}], "total": 2},
    ]

    def fake_request(method, path, payload):
        calls.append((method, path, payload))
        return responses.pop(0)

    monkeypatch.setattr(adapter, "_request", fake_request)
    rows = adapter.list_auto_add_products(
        "1977747", auto_add_date="2026-10-08T21:00:00Z", limit=1
    )

    assert [r["product_id"] for r in rows] == [1, 2]
    assert calls[0][0:2] == ("POST", "/v1/actions/auto-add/products/list")
    assert calls[0][2]["action_id"] == 1977747
    assert calls[0][2]["auto_add_date"] == "2026-10-08T21:00:00Z"
    assert calls[0][2]["limit"] == 1
    assert calls[0][2]["offset"] == 0
    assert calls[1][2]["offset"] == 1


def test_list_promotions_preserves_raw_auto_add_dates(monkeypatch):
    adapter = OzonPromotionsAdapter(
        OzonCredentials("cid", "key"), "https://example.invalid", 10, use_sdk=True
    )
    raw = {
        "result": [{
            "id": 1977747,
            "title": "Эластичный бустинг. Без ограничения срока действия",
            "action_type": "ELASTIC_BOOSTING",
            "auto_add_dates": ["2026-10-08T21:00:00Z"],
        }]
    }

    def fake_request(method, path, payload=None):
        assert method == "GET"
        assert path == "/v1/actions"
        return raw

    monkeypatch.setattr(adapter, "_request", fake_request)
    promotions = adapter.list_promotions()

    assert len(promotions) == 1
    assert promotions[0].action_id == "1977747"
    assert promotions[0].metadata["auto_add_dates"] == ["2026-10-08T21:00:00Z"]


def test_auto_add_delete_adapter_contract(monkeypatch):
    adapter = OzonPromotionsAdapter(OzonCredentials("cid", "key"), "https://example.invalid", 10)
    calls = []

    def fake_request(method, path, payload, *, return_status=False):
        calls.append((method, path, payload, return_status))
        return ({"product_ids": [101, 102]}, 200) if return_status else {"product_ids": [101, 102]}

    monkeypatch.setattr(adapter, "_request", fake_request)
    result = adapter.delete_auto_add_products(
        "1977747",
        auto_add_date="2026-10-08T21:00:00Z",
        product_ids=["101", "102"],
    )
    assert result.deactivated_product_ids == ("101", "102")
    assert calls[0][0:2] == ("POST", "/v1/actions/auto-add/products/delete")
    assert calls[0][2] == {
        "action_id": 1977747,
        "auto_add_date": "2026-10-08T21:00:00Z",
        "product_ids": [101, 102],
    }


def test_auto_add_delete_threshold_and_fresh_check():
    from app.services.auto_add import AutoAddDeleteService, row_safety_diffs

    rows = [
        {"product_id": 1, "price": 1000, "action_price_to_auto_add": 900},
        {"product_id": 2, "price": 1000, "action_price_to_auto_add": 940},
    ]
    assert AutoAddDeleteService._discount(rows[0]) == Decimal("10")
    assert AutoAddDeleteService._discount(rows[1]) == Decimal("6")
    assert row_safety_diffs(rows[0], {**rows[0], "action_price_to_auto_add": 901}) == ["action_price_to_auto_add"]


def test_auto_add_delete_service_requires_fresh_state_and_snapshots():
    from app.services.auto_add import AutoAddDeleteService

    class Repo:
        def __init__(self):
            self.operations = []
            self.snapshots = []
        def save_operation(self, op):
            self.operations.append(op)
        def save_snapshot(self, snapshot_id, operation_id, items):
            self.snapshots.append((snapshot_id, operation_id, list(items)))

    class Adapter:
        def __init__(self):
            self.rows = [{"product_id": 1, "price": 1000, "action_price_to_auto_add": 800, "name": "A"}]
            self.deleted = []
        def list_auto_add_products(self, action_id, *, auto_add_date, limit=100):
            return [dict(r) for r in self.rows]
        def delete_auto_add_products(self, action_id, *, auto_add_date, product_ids):
            self.deleted.extend(product_ids)
            self.rows = [r for r in self.rows if str(r["product_id"]) not in set(product_ids)]
            from app.domain.models import MutationResult
            return MutationResult(deactivated_product_ids=tuple(product_ids), transport_status=200)

    repo = Repo()
    adapter = Adapter()
    service = AutoAddDeleteService(adapter, repo)
    rows = list(adapter.rows)
    op = service.build_operation("1977747", "2026-10-08T21:00:00Z", rows, Decimal("5"), "test")
    op, result = service.execute(op, "2026-10-08T21:00:00Z", {"1": rows[0]}, "test")
    assert op.status.value == "SUCCESS"
    assert result.deactivated_product_ids == ("1",)
    assert adapter.deleted == ["1"]
    assert len(repo.snapshots) == 1


def test_auto_add_delete_service_blocks_changed_price():
    from app.services.auto_add import AutoAddDeleteService

    class Repo:
        def save_operation(self, op): pass
        def save_snapshot(self, snapshot_id, operation_id, items): pass

    class Adapter:
        def list_auto_add_products(self, action_id, *, auto_add_date, limit=100):
            return [{"product_id": 1, "price": 999, "action_price_to_auto_add": 800}]

    service = AutoAddDeleteService(Adapter(), Repo())
    preview = {"product_id": 1, "price": 1000, "action_price_to_auto_add": 800}
    op = service.build_operation("1977747", "2026-10-08T21:00:00Z", [preview], Decimal("5"), "test")
    try:
        service.execute(op, "2026-10-08T21:00:00Z", {"1": preview}, "test")
    except RuntimeError as exc:
        assert "Fresh Check Auto-Add" in str(exc)
    else:
        raise AssertionError("Changed Auto-Add price must block mutation")


def test_auto_add_delete_reconciliation_confirms_removed_state():
    from app.services.auto_add import AutoAddDeleteService

    class Repo:
        def __init__(self): self.saved = []
        def save_operation(self, op): self.saved.append(op)
        def save_snapshot(self, snapshot_id, operation_id, items): pass

    class Adapter:
        def __init__(self): self.calls = 0
        def list_auto_add_products(self, action_id, *, auto_add_date, limit=100):
            self.calls += 1
            if self.calls <= 2:
                return [{"product_id": 1, "price": 1000, "action_price_to_auto_add": 800}]
            return []
        def delete_auto_add_products(self, action_id, *, auto_add_date, product_ids):
            from app.domain.models import MutationResult
            return MutationResult(deactivated_product_ids=tuple(product_ids), transport_status=200)

    adapter = Adapter(); repo = Repo()
    service = AutoAddDeleteService(adapter, repo)
    preview = {"1": {"product_id": 1, "price": 1000, "action_price_to_auto_add": 800}}
    op = service.build_operation("1977747", "2026-10-08T21:00:00Z", list(preview.values()), Decimal("5"), "test")
    op, _ = service.execute(op, "2026-10-08T21:00:00Z", preview, "test")
    assert op.status.value == "SUCCESS"
    assert op.items[0].verification_result == "CONFIRMED_REMOVED"
    assert op.items[0].status.value == "SUCCESS"


def test_auto_add_delete_reconciliation_still_present_is_partial():
    from app.services.auto_add import AutoAddDeleteService

    class Repo:
        def save_operation(self, op): pass
        def save_snapshot(self, snapshot_id, operation_id, items): pass

    class Adapter:
        def list_auto_add_products(self, action_id, *, auto_add_date, limit=100):
            return [{"product_id": 1, "price": 1000, "action_price_to_auto_add": 800}]
        def delete_auto_add_products(self, action_id, *, auto_add_date, product_ids):
            from app.domain.models import MutationResult
            return MutationResult(deactivated_product_ids=tuple(product_ids), transport_status=200)

    service = AutoAddDeleteService(Adapter(), Repo())
    preview = {"1": {"product_id": 1, "price": 1000, "action_price_to_auto_add": 800}}
    op = service.build_operation("1977747", "2026-10-08T21:00:00Z", list(preview.values()), Decimal("5"), "test")
    op, _ = service.execute(op, "2026-10-08T21:00:00Z", preview, "test")
    assert op.status.value == "VERIFICATION_FAILED"
    assert op.items[0].verification_result == "STILL_PRESENT"
    assert op.items[0].status.value == "UNKNOWN_RESULT"


def test_auto_add_delete_reconciliation_read_error_is_unknown():
    from app.services.auto_add import AutoAddDeleteService

    class Repo:
        def save_operation(self, op): pass
        def save_snapshot(self, snapshot_id, operation_id, items): pass

    class Adapter:
        def __init__(self): self.calls = 0
        def list_auto_add_products(self, action_id, *, auto_add_date, limit=100):
            self.calls += 1
            if self.calls == 1:
                return [{"product_id": 1, "price": 1000, "action_price_to_auto_add": 800}]
            if self.calls == 2:
                return [{"product_id": 1, "price": 1000, "action_price_to_auto_add": 800}]
            raise TimeoutError("reconciliation timeout")
        def delete_auto_add_products(self, action_id, *, auto_add_date, product_ids):
            from app.domain.models import MutationResult
            return MutationResult(deactivated_product_ids=tuple(product_ids), transport_status=200)

    service = AutoAddDeleteService(Adapter(), Repo())
    preview = {"1": {"product_id": 1, "price": 1000, "action_price_to_auto_add": 800}}
    op = service.build_operation("1977747", "2026-10-08T21:00:00Z", list(preview.values()), Decimal("5"), "test")
    try:
        service.execute(op, "2026-10-08T21:00:00Z", preview, "test")
    except TimeoutError:
        pass
    else:
        raise AssertionError("Reconciliation read failure must remain UNKNOWN")
    assert op.status.value == "VERIFICATION_FAILED"
    assert op.items[0].verification_result == "UNKNOWN"
    assert op.items[0].status.value == "UNKNOWN_RESULT"


def test_auto_add_update_adapter_contract(monkeypatch):
    adapter = OzonPromotionsAdapter(OzonCredentials("cid", "key"), "https://example.invalid", 10)
    calls = []

    def fake_request(method, path, payload, *, return_status=False):
        calls.append((method, path, payload, return_status))
        return ({"product_ids": [101], "warnings": []}, 200) if return_status else {"product_ids": [101]}

    monkeypatch.setattr(adapter, "_request", fake_request)
    result = adapter.update_auto_add_products(
        "1977747",
        auto_add_date="2026-10-08T21:00:00Z",
        products=[{"product_id": "101", "action_price": Decimal("981"), "currency": "RUB"}],
    )
    assert result.active_product_ids == ("101",)
    assert calls[0][0:2] == ("POST", "/v2/actions/auto-add/products/update")
    assert calls[0][2] == {
        "action_id": 1977747,
        "auto_add_date": "2026-10-08T21:00:00Z",
        "products": [{"id": 101, "action_price": {"amount": "981", "currency": "RUB"}}],
    }


def _make_auto_add_rollback_source(tmp_path):
    from app.domain.models import SnapshotItem
    from app.repositories.sqlite import SQLiteRepository
    repo = SQLiteRepository(tmp_path / "auto-add-rollback.db")
    # Source operation only needs to exist because snapshot rows reference it.
    from app.services.workflow import OperationFactory
    source = OperationFactory.create("1977747", "tester", operation_type="AUTO_ADD_DELETE")
    repo.save_operation(source)
    repo.save_snapshot("source-snap", source.operation_id, [SnapshotItem(
        action_id="1977747", product_id="101", price=Decimal("1000"), action_price=Decimal("981"),
        current_boost=None, min_boost=None, max_boost=None, price_min_elastic=None, price_max_elastic=Decimal("950"),
        membership="auto_add", timestamp="2026-10-02T00:00:00Z", auto_add_date="2026-10-08T21:00:00Z", present=True,
    )])
    return repo


def test_auto_add_rollback_restores_and_reconciles(tmp_path):
    from app.services.auto_add import AutoAddRollbackService
    from app.domain.models import MutationResult

    class Adapter:
        def __init__(self):
            self.rows = []
            self.update_calls = []
        def list_auto_add_products(self, action_id, *, auto_add_date, limit=100):
            return [dict(x) for x in self.rows]
        def update_auto_add_products(self, action_id, *, auto_add_date, products):
            self.update_calls.append(products)
            self.rows = [{"product_id": p["product_id"], "action_price_to_auto_add": p["action_price"]} for p in products]
            return MutationResult(active_product_ids=tuple(str(p["product_id"]) for p in products), transport_status=200)

    repo = _make_auto_add_rollback_source(tmp_path)
    adapter = Adapter()
    service = AutoAddRollbackService(adapter, repo)
    op = service.prepare("source-snap", "tester")
    assert op.status.value == "PREVIEWED"
    assert op.items[0].requested_action_price == Decimal("981")
    op, result = service.execute(op, "tester")
    assert op.status.value == "SUCCESS"
    assert op.items[0].verification_result == "CONFIRMED_RESTORED"
    assert result.active_product_ids == ("101",)
    assert adapter.update_calls[0][0]["product_id"] == "101"
    assert repo.get_snapshot(op.snapshot_id)[0]["present"] == 0


def test_auto_add_rollback_blocks_if_product_reappeared(tmp_path):
    from app.services.auto_add import AutoAddRollbackService
    repo = _make_auto_add_rollback_source(tmp_path)

    class Adapter:
        def list_auto_add_products(self, action_id, *, auto_add_date, limit=100):
            return [{"product_id": "101", "action_price_to_auto_add": 981}]

    with pytest.raises(ValueError, match="уже присутствуют"):
        AutoAddRollbackService(Adapter(), repo).prepare("source-snap", "tester")


def test_auto_add_rollback_reconciliation_price_mismatch_is_unknown(tmp_path):
    from app.services.auto_add import AutoAddRollbackService
    from app.domain.models import MutationResult
    repo = _make_auto_add_rollback_source(tmp_path)

    class Adapter:
        def __init__(self): self.calls = 0
        def list_auto_add_products(self, action_id, *, auto_add_date, limit=100):
            self.calls += 1
            if self.calls <= 3:
                return []
            return [{"product_id": "101", "action_price_to_auto_add": 980}]
        def update_auto_add_products(self, action_id, *, auto_add_date, products):
            return MutationResult(active_product_ids=("101",), transport_status=200)

    adapter = Adapter()
    op = AutoAddRollbackService(adapter, repo).prepare("source-snap", "tester")
    op, _ = AutoAddRollbackService(adapter, repo).execute(op, "tester")
    assert op.status.value == "VERIFICATION_FAILED"
    assert op.items[0].verification_result == "RESTORED_PRICE_MISMATCH"
    assert op.items[0].status.value == "UNKNOWN_RESULT"


def test_auto_add_delete_threshold_can_be_negative():
    from app.services.auto_add import AutoAddDeleteService

    class Repo:
        def save_operation(self, op):
            pass
        def save_snapshot(self, snapshot_id, operation_id, items):
            pass

    service = AutoAddDeleteService(adapter=None, repository=Repo())
    rows = [
        {"product_id": 1, "price": 1000, "action_price_to_auto_add": 1050},  # -5%
        {"product_id": 2, "price": 1000, "action_price_to_auto_add": 1030},  # -3%
    ]
    operation = service.build_operation(
        "1977747", "2026-10-08T21:00:00Z", rows, Decimal("-4"), "test"
    )
    assert [item.product_id for item in operation.items] == ["2"]
