from pathlib import Path

from app.adapters.mock import MockOzonAdapter
from app.domain.models import ProductState, Promotion
from app.repositories.sqlite import SQLiteRepository
from app.services.stocks import StockChange, StockService


def _adapter():
    return MockOzonAdapter(
        [Promotion("1977747", "Mock", "active")],
        [ProductState("1977747", "101", "OFF-101", "Test", None, 0, None, None, None, None, None, "active", "available")],
    )


def _change(free=8):
    return StockChange(
        product_id="101", sku="101", offer_id="OFF-101", warehouse_id=1001,
        warehouse_name="Mock FBS warehouse", old_present=10, old_reserved=2,
        old_free_stock=free, requested_free_stock=free + 3,
    )


def test_stock_read_has_warehouse_and_free_reserved_fields():
    adapter = _adapter()
    rows = adapter.list_stocks_by_warehouse()
    assert rows[0]["warehouse_id"] == 1001
    assert rows[0]["present"] == 10
    assert rows[0]["reserved"] == 2
    assert rows[0]["free_stock"] == 8


def test_stock_update_requires_explicit_confirmation_and_snapshot(tmp_path):
    adapter = _adapter()
    repo = SQLiteRepository(tmp_path / "stocks.sqlite")
    service = StockService(adapter, repo)
    plan = service.prepare([_change()])
    assert repo.get_stock_snapshot(plan["snapshot_id"])
    try:
        service.execute(plan, confirmed=False)
    except ValueError as exc:
        assert "подтверждения" in str(exc)
    else:
        raise AssertionError("mutation without confirmation must be blocked")


def test_stock_update_changes_free_stock_and_reconciles(tmp_path):
    adapter = _adapter()
    repo = SQLiteRepository(tmp_path / "stocks.sqlite")
    service = StockService(adapter, repo)
    plan = service.prepare([_change()])
    result = service.execute(plan, confirmed=True)
    assert result["status"] == "SUCCESS"
    assert result["success_count"] == 1
    assert adapter.list_stocks_by_warehouse()[0]["free_stock"] == 11


def test_stock_fresh_check_blocks_changed_value(tmp_path):
    adapter = _adapter()
    repo = SQLiteRepository(tmp_path / "stocks.sqlite")
    service = StockService(adapter, repo)
    plan = service.prepare([_change()])
    # Materialize mock row first, then change it.
    adapter.stock_rows["101:1001"] = {
        **adapter.list_stocks_by_warehouse()[0], "free_stock": 20, "present": 22,
    }
    try:
        service.execute(plan, confirmed=True)
    except ValueError as exc:
        assert "Fresh Check" in str(exc)
    else:
        raise AssertionError("changed stock must block mutation")


def test_stock_partial_api_results_are_persisted(tmp_path):
    class PartialAdapter(MockOzonAdapter):
        def update_stocks(self, stocks):
            result = super().update_stocks(stocks[:1])
            exc = RuntimeError("timeout after first batch")
            exc.partial_results = result
            raise exc

    adapter = PartialAdapter(
        [Promotion("1977747", "Mock", "active")],
        [ProductState("1977747", "101", "OFF-101", "Test", None, 0, None, None, None, None, None, "active", "available")],
    )
    repo = SQLiteRepository(tmp_path / "stocks.sqlite")
    service = StockService(adapter, repo)
    plan = service.prepare([_change()])
    try:
        service.execute(plan, confirmed=True)
    except RuntimeError:
        pass
    else:
        raise AssertionError("unknown transport result must be surfaced")
    rows = repo.list_stock_operation_items(plan["operation_id"])
    assert rows[0]["status"] == "SUCCESS"

class _Response:
    def __init__(self, status=200, data=None):
        self.status_code = status
        self._data = data or {}
        self.content = b"{}"
    def json(self):
        return self._data


class _Session:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []
        self.headers = {}
    def request(self, method, url, json=None, timeout=None):
        self.calls.append((method, url, json, timeout))
        return self.responses.pop(0)


def test_ozon_adapter_stock_contract_and_cursor():
    from app.adapters.ozon import OzonCredentials, OzonPromotionsAdapter
    session = _Session([
        _Response(data={"items": [{"id": 1, "offer_id": "A"}, {"id": 2, "offer_id": "B"}], "last_id": ""}),
        _Response(data={"products": [
            {"product_id": 1, "sku": 11, "offer_id": "A", "warehouse_id": 9, "warehouse_name": "W", "present": 7, "reserved": 2, "free_stock": 5},
            {"product_id": 2, "sku": 22, "offer_id": "B", "warehouse_id": 9, "warehouse_name": "W", "present": 4, "reserved": 1, "free_stock": 3},
        ], "cursor": "", "has_next": False}),
        _Response(data={"result": [{"product_id": 1, "warehouse_id": 9, "updated": True, "errors": []}]}),
    ])
    adapter = OzonPromotionsAdapter(OzonCredentials("1", "secret"), session=session, use_sdk=False)
    rows = adapter.list_stocks_by_warehouse()
    assert [r["product_id"] for r in rows] == ["1", "2"]
    assert session.calls[0][2] == {"limit": 1000, "filter": {"visibility": "ALL"}}
    assert session.calls[1][2] == {"limit": 1000, "offer_id": ["A", "B"]}
    result = adapter.update_stocks([{"product_id": "1", "warehouse_id": 9, "stock": 12}])
    assert result[0]["updated"] is True
    assert session.calls[-1][2] == {"stocks": [{"product_id": 1, "warehouse_id": 9, "stock": 12}]}


def test_ozon_adapter_unwraps_product_list_result():
    from app.adapters.ozon import OzonCredentials, OzonPromotionsAdapter
    session = _Session([
        _Response(data={"result": {"items": [{"id": 7, "offer_id": "R"}], "last_id": "next"}}),
        _Response(data={"result": {"items": [{"id": 8, "offer_id": "S"}], "last_id": ""}}),
        _Response(data={"products": [
            {"product_id": 7, "sku": 70, "offer_id": "R", "warehouse_id": 9, "warehouse_name": "W", "present": 1, "reserved": 0, "free_stock": 1},
            {"product_id": 8, "sku": 80, "offer_id": "S", "warehouse_id": 9, "warehouse_name": "W", "present": 2, "reserved": 0, "free_stock": 2},
        ], "cursor": "", "has_next": False}),
    ])
    adapter = OzonPromotionsAdapter(OzonCredentials("1", "secret"), session=session, use_sdk=False)
    rows = adapter.list_stocks_by_warehouse()
    assert [r["product_id"] for r in rows] == ["7", "8"]
    assert session.calls[0][2] == {"limit": 1000, "filter": {"visibility": "ALL"}}


def test_ozon_adapter_stock_v2_uses_array_offer_id_and_cursor_pagination():
    from app.adapters.ozon import OzonCredentials, OzonPromotionsAdapter
    session = _Session([
        _Response(data={"items": [{"id": 1, "offer_id": "A"}], "last_id": ""}),
        _Response(data={"products": [{"product_id": 1, "sku": 11, "offer_id": "A", "warehouse_id": 9, "warehouse_name": "W1", "present": 7, "reserved": 2, "free_stock": 5}], "cursor": "next", "has_next": True}),
        _Response(data={"products": [{"product_id": 1, "sku": 11, "offer_id": "A", "warehouse_id": 10, "warehouse_name": "W2", "present": 4, "reserved": 1, "free_stock": 3}], "cursor": "", "has_next": False}),
    ])
    adapter = OzonPromotionsAdapter(OzonCredentials("1", "secret"), session=session, use_sdk=False)
    rows = adapter.list_stocks_by_warehouse()
    assert len(rows) == 2
    assert session.calls[1][2] == {"limit": 1000, "offer_id": ["A"]}
    assert session.calls[2][2] == {"limit": 1000, "offer_id": ["A"], "cursor": "next"}


def test_ozon_adapter_batches_more_than_1000_offer_ids():
    from app.adapters.ozon import OzonCredentials, OzonPromotionsAdapter

    offers = [{"id": i, "offer_id": f"O-{i}"} for i in range(1001)]
    first_products = [
        {"product_id": i, "sku": i + 10000, "offer_id": f"O-{i}", "warehouse_id": 9,
         "warehouse_name": "W", "present": 1, "reserved": 0, "free_stock": 1}
        for i in range(1000)
    ]
    second_products = [{
        "product_id": 1000, "sku": 11000, "offer_id": "O-1000", "warehouse_id": 9,
        "warehouse_name": "W", "present": 2, "reserved": 0, "free_stock": 2,
    }]
    session = _Session([
        _Response(data={"items": offers, "last_id": ""}),
        _Response(data={"products": first_products, "cursor": "", "has_next": False}),
        _Response(data={"products": second_products, "cursor": "", "has_next": False}),
    ])
    adapter = OzonPromotionsAdapter(OzonCredentials("1", "secret"), session=session, use_sdk=False)
    rows = adapter.list_stocks_by_warehouse()
    assert len(rows) == 1001
    assert len(session.calls) == 3
    assert len(session.calls[1][2]["offer_id"]) == 1000
    assert len(session.calls[2][2]["offer_id"]) == 1


def test_ozon_adapter_classifies_429_as_rate_limit():
    from app.adapters.ozon import OzonAPIError, OzonCredentials, OzonPromotionsAdapter
    session = _Session([_Response(status=429, data={"message": "too many"})])
    adapter = OzonPromotionsAdapter(OzonCredentials("1", "secret"), session=session, use_sdk=False)
    try:
        adapter.list_stocks_by_warehouse()
    except OzonAPIError as exc:
        assert exc.status_code == 429
        assert exc.category == "RATE_LIMIT"
    else:
        raise AssertionError("429 must be classified as RATE_LIMIT")


def test_900_stock_changes_stress_without_real_ozon(tmp_path):
    products = [
        ProductState("1977747", str(i), f"OFF-{i}", f"Product {i}", None, 0, None, None, None, None, None, "active", "available")
        for i in range(1, 901)
    ]
    adapter = MockOzonAdapter([Promotion("1977747", "Mock", "active")], products)
    repo = SQLiteRepository(tmp_path / "stocks.sqlite")
    service = StockService(adapter, repo)
    source = adapter.list_stocks_by_warehouse()
    changes = [
        StockChange(
            product_id=r["product_id"], sku=r["sku"], offer_id=r["offer_id"],
            warehouse_id=r["warehouse_id"], warehouse_name=r["warehouse_name"],
            old_present=r["present"], old_reserved=r["reserved"], old_free_stock=r["free_stock"],
            requested_free_stock=r["free_stock"] + 1,
        ) for r in source
    ]
    plan = service.prepare(changes)
    result = service.execute(plan, confirmed=True)
    assert result["status"] == "SUCCESS"
    assert result["success_count"] == 900
    assert result["failed_count"] == 0


def test_stock_read_after_write_persists_actual_values(tmp_path):
    adapter = _adapter()
    repo = SQLiteRepository(tmp_path / "stocks.sqlite")
    service = StockService(adapter, repo)
    plan = service.prepare([_change(free=8)])
    result = service.execute(plan, confirmed=True)
    assert result["status"] == "SUCCESS"
    row = dict(repo.list_stock_operation_items(plan["operation_id"])[0])
    assert row["actual_free_stock"] == 11
    assert row["actual_reserved"] == 2
    assert row["actual_present"] == 13


def test_stock_read_after_write_mismatch_is_verification_failed(tmp_path):
    class MismatchAdapter(MockOzonAdapter):
        def update_stocks(self, stocks):
            result = super().update_stocks(stocks)
            key = f"{stocks[0]['product_id']}:{stocks[0]['warehouse_id']}"
            row = dict(self.stock_rows[key])
            row["free_stock"] += 1
            row["present"] += 1
            self.stock_rows[key] = row
            return result

    adapter = MismatchAdapter(
        [Promotion("1977747", "Mock", "active")],
        [ProductState("1977747", "101", "OFF-101", "Test", None, 0, None, None, None, None, None, "active", "available")],
    )
    repo = SQLiteRepository(tmp_path / "stocks.sqlite")
    service = StockService(adapter, repo)
    plan = service.prepare([_change()])
    result = service.execute(plan, confirmed=True)
    assert result["status"] == "FAILED"
    row = dict(repo.list_stock_operation_items(plan["operation_id"])[0])
    assert row["status"] == "VERIFICATION_FAILED"
    assert row["actual_free_stock"] == 12


def test_stock_rollback_restores_snapshot_target(tmp_path):
    adapter = _adapter()
    repo = SQLiteRepository(tmp_path / "stocks.sqlite")
    service = StockService(adapter, repo)
    first = service.prepare([_change()])
    service.execute(first, confirmed=True)
    assert adapter.list_stocks_by_warehouse()[0]["free_stock"] == 11

    rollback = service.prepare_rollback(first["snapshot_id"])
    assert rollback["changes"][0].requested_free_stock == 8
    result = service.execute(rollback, confirmed=True)
    assert result["status"] == "SUCCESS"
    assert adapter.list_stocks_by_warehouse()[0]["free_stock"] == 8


def test_stock_rollback_is_blocked_when_current_state_changed(tmp_path):
    adapter = _adapter()
    repo = SQLiteRepository(tmp_path / "stocks.sqlite")
    service = StockService(adapter, repo)
    first = service.prepare([_change()])
    service.execute(first, confirmed=True)
    adapter.stock_rows["101:1001"] = {**adapter.list_stocks_by_warehouse()[0], "free_stock": 20, "present": 22}
    # Rollback preparation must target the immutable snapshot but also start
    # from the actual current state; the next prepare/execute Fresh Check must
    # not silently use the stale UI state.
    rollback = service.prepare_rollback(first["snapshot_id"])
    assert rollback["changes"][0].old_free_stock == 20
    assert rollback["changes"][0].requested_free_stock == 8


def test_stock_mutation_batches_101_pairs_at_100():
    class BatchRecordingAdapter:
        def __init__(self):
            self.calls = []
        def update_stocks(self, stocks):
            self.calls.append(list(stocks))
            return [{"product_id": int(x["product_id"]), "warehouse_id": int(x["warehouse_id"]), "updated": True, "errors": []} for x in stocks]

    adapter = BatchRecordingAdapter()
    from app.adapters.ozon import OzonCredentials, OzonPromotionsAdapter
    session = _Session([
        _Response(data={"result": [{"product_id": i, "warehouse_id": 9, "updated": True, "errors": []} for i in range(100)]}),
        _Response(data={"result": [{"product_id": 100, "warehouse_id": 9, "updated": True, "errors": []}]}),
    ])
    ozon = OzonPromotionsAdapter(OzonCredentials("1", "secret"), session=session, use_sdk=False)
    result = ozon.update_stocks([{"product_id": i, "warehouse_id": 9, "stock": i + 1} for i in range(101)])
    assert len(result) == 101
    assert len(session.calls) == 2
    assert len(session.calls[0][2]["stocks"]) == 100
    assert len(session.calls[1][2]["stocks"]) == 1


def test_stock_mutation_429_is_not_retried():
    from app.adapters.ozon import OzonAPIError, OzonCredentials, OzonPromotionsAdapter
    session = _Session([_Response(status=429, data={"message": "too many"})])
    adapter = OzonPromotionsAdapter(OzonCredentials("1", "secret"), session=session, use_sdk=False)
    try:
        adapter.update_stocks([{"product_id": 1, "warehouse_id": 9, "stock": 5}])
    except OzonAPIError as exc:
        assert exc.category == "RATE_LIMIT"
        assert len(session.calls) == 1
    else:
        raise AssertionError("429 mutation must stop without blind retry")


def test_stock_mutation_timeout_is_unknown_result_and_not_retried():
    import requests
    from app.adapters.ozon import OzonAPIError, OzonCredentials, OzonPromotionsAdapter
    class TimeoutSession(_Session):
        def request(self, method, url, json=None, timeout=None):
            self.calls.append((method, url, json, timeout))
            raise requests.Timeout("timeout")
    session = TimeoutSession([])
    adapter = OzonPromotionsAdapter(OzonCredentials("1", "secret"), session=session, use_sdk=False)
    try:
        adapter.update_stocks([{"product_id": 1, "warehouse_id": 9, "stock": 5}])
    except OzonAPIError as exc:
        assert exc.category == "UNKNOWN_RESULT"
        assert len(session.calls) == 1
    else:
        raise AssertionError("timeout mutation must be UNKNOWN_RESULT")


def test_stock_fresh_check_blocks_reserved_change(tmp_path):
    adapter = _adapter()
    repo = SQLiteRepository(tmp_path / "stocks.sqlite")
    service = StockService(adapter, repo)
    plan = service.prepare([_change()])
    adapter.stock_rows["101:1001"] = {
        **adapter.list_stocks_by_warehouse()[0], "reserved": 5, "present": 13, "free_stock": 8,
    }
    try:
        service.execute(plan, confirmed=True)
    except ValueError as exc:
        assert "Fresh Check" in str(exc)
    else:
        raise AssertionError("reserved change must block mutation")


def test_stock_partial_normal_response_is_persisted(tmp_path):
    class PartialResponseAdapter(MockOzonAdapter):
        def update_stocks(self, stocks):
            result = super().update_stocks(stocks[:1])
            return result

    adapter = PartialResponseAdapter(
        [Promotion("1977747", "Mock", "active")],
        [
            ProductState("1977747", "101", "OFF-101", "Test 1", None, 0, None, None, None, None, None, "active", "available"),
            ProductState("1977747", "102", "OFF-102", "Test 2", None, 0, None, None, None, None, None, "active", "available"),
        ],
    )
    repo = SQLiteRepository(tmp_path / "stocks.sqlite")
    service = StockService(adapter, repo)
    source = adapter.list_stocks_by_warehouse()
    changes = [
        StockChange(
            product_id=r["product_id"], sku=r["sku"], offer_id=r["offer_id"], warehouse_id=r["warehouse_id"],
            warehouse_name=r["warehouse_name"], old_present=r["present"], old_reserved=r["reserved"],
            old_free_stock=r["free_stock"], requested_free_stock=r["free_stock"] + 1,
        ) for r in source
    ]
    plan = service.prepare(changes)
    result = service.execute(plan, confirmed=True)
    assert result["status"] == "PARTIAL"
    assert result["success_count"] == 1
    assert result["failed_count"] == 1
    rows = {r["product_id"]: dict(r) for r in repo.list_stock_operation_items(plan["operation_id"])}
    assert rows["101"]["status"] == "SUCCESS"
    assert rows["102"]["status"] == "FAILED"


def test_stock_read_after_write_transport_failure_is_unknown_and_not_retried(tmp_path):
    class VerifyFailAdapter(MockOzonAdapter):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.read_calls = 0
            self.write_calls = 0

        def update_stocks(self, stocks):
            self.write_calls += 1
            return super().update_stocks(stocks)

        def list_stocks_by_warehouse(self):
            self.read_calls += 1
            # First read is Preview Fresh Check; second read is mutation
            # verification and must fail after the write has already happened.
            if self.read_calls >= 3:
                raise RuntimeError("verification transport failure")
            return super().list_stocks_by_warehouse()

    adapter = VerifyFailAdapter(
        [Promotion("1977747", "Mock", "active")],
        [ProductState("1977747", "101", "OFF-101", "Test", None, 0, None, None, None, None, None, "active", "available")],
    )
    repo = SQLiteRepository(tmp_path / "stocks.sqlite")
    service = StockService(adapter, repo)
    plan = service.prepare([_change()])

    try:
        service.execute(plan, confirmed=True)
    except RuntimeError as exc:
        assert "неизвестен" in str(exc)
    else:
        raise AssertionError("verification transport failure must surface UNKNOWN_RESULT")

    assert adapter.write_calls == 1
    assert adapter.stock_rows["101:1001"]["free_stock"] == 11
    row = dict(repo.list_stock_operation_items(plan["operation_id"])[0])
    assert row["status"] == "UNKNOWN_RESULT"
    operation = dict(repo.list_stock_operations(limit=1)[0])
    assert operation["status"] == "UNKNOWN_RESULT"


def test_stock_duplicate_product_warehouse_is_rejected_before_mutation(tmp_path):
    adapter = _adapter()
    repo = SQLiteRepository(tmp_path / "stocks.sqlite")
    service = StockService(adapter, repo)
    change = _change()
    duplicate = StockChange(**{**change.__dict__, "requested_free_stock": 12})
    try:
        service.prepare([change, duplicate])
    except ValueError as exc:
        assert "Дубликат товар–склад" in str(exc)
    else:
        raise AssertionError("duplicate product-warehouse pair must be rejected")


def test_stock_negative_value_is_rejected_before_snapshot(tmp_path):
    adapter = _adapter()
    repo = SQLiteRepository(tmp_path / "stocks.sqlite")
    service = StockService(adapter, repo)
    change = StockChange(**{**_change().__dict__, "requested_free_stock": -1})
    try:
        service.prepare([change])
    except ValueError as exc:
        assert "отрицательным" in str(exc)
    else:
        raise AssertionError("negative stock must be rejected")
    assert repo.list_stock_operations(limit=10) == []


def test_stock_adapter_batches_900_mutations_without_retry():
    from app.adapters.ozon import OzonCredentials, OzonPromotionsAdapter

    responses = []
    for start in (0, 100, 200, 300, 400, 500, 600, 700, 800):
        size = min(100, 900 - start)
        responses.append(_Response(data={"result": [
            {"product_id": i, "warehouse_id": 9, "updated": True, "errors": []}
            for i in range(start, start + size)
        ]}))
    session = _Session(responses)
    adapter = OzonPromotionsAdapter(OzonCredentials("1", "secret"), session=session, use_sdk=False)
    payload = [{"product_id": i, "warehouse_id": 9, "stock": i + 1} for i in range(900)]
    result = adapter.update_stocks(payload)
    assert len(result) == 900
    assert len(session.calls) == 9
    assert all(len(call[2]["stocks"]) == 100 for call in session.calls)


def test_stock_partial_transport_failure_does_not_retry_completed_batch(tmp_path):
    from app.adapters.ozon import OzonAPIError, OzonCredentials, OzonPromotionsAdapter

    responses = [
        _Response(data={"result": [
            {"product_id": i, "warehouse_id": 9, "updated": True, "errors": []}
            for i in range(100)
        ]}),
        _Response(status=429, data={"message": "too many"}),
    ]
    session = _Session(responses)
    adapter = OzonPromotionsAdapter(OzonCredentials("1", "secret"), session=session, use_sdk=False)
    try:
        adapter.update_stocks([{"product_id": i, "warehouse_id": 9, "stock": i + 1} for i in range(101)])
    except OzonAPIError as exc:
        assert exc.category == "RATE_LIMIT"
        assert len(exc.partial_results) == 100
        assert getattr(exc, "failed_batch_offset") == 100
        assert len(session.calls) == 2
    else:
        raise AssertionError("second batch 429 must surface without retry")


def test_stock_execute_cannot_repeat_terminal_operation(tmp_path):
    adapter = _adapter()
    repo = SQLiteRepository(tmp_path / "stocks.sqlite")
    service = StockService(adapter, repo)
    plan = service.prepare([_change()])
    service.execute(plan, confirmed=True)
    calls_before = list(getattr(adapter, "update_calls", []))
    try:
        service.execute(plan, confirmed=True)
    except ValueError as exc:
        assert "уже завершена" in str(exc)
    else:
        raise AssertionError("terminal stock operation must not be executed twice")
    assert list(getattr(adapter, "update_calls", [])) == calls_before


def test_stock_execute_requires_persisted_snapshot(tmp_path):
    adapter = _adapter()
    repo = SQLiteRepository(tmp_path / "stocks.sqlite")
    service = StockService(adapter, repo)
    plan = service.prepare([_change()])
    with repo.connect() as con:
        con.execute("DELETE FROM stock_snapshots WHERE snapshot_id=?", (plan["snapshot_id"],))
    try:
        service.execute(plan, confirmed=True)
    except ValueError as exc:
        assert "Snapshot отсутствует" in str(exc)
    else:
        raise AssertionError("mutation must be blocked when snapshot disappeared")
    assert adapter.stock_rows.get("101:1001") is None


def test_stock_multi_batch_partial_failure_is_unknown_and_first_batch_is_not_retried(tmp_path):
    class BatchFailAdapter(MockOzonAdapter):
        def __init__(self, promotions, products):
            super().__init__(promotions, products)
            self.calls = []

        def update_stocks(self, stocks):
            results = []
            for start in range(0, len(stocks), 100):
                batch = stocks[start:start + 100]
                self.calls.append(list(batch))
                if len(self.calls) == 2:
                    from app.adapters.ozon import OzonAPIError
                    exc = OzonAPIError("rate limit on second batch", status_code=429, category="RATE_LIMIT")
                    exc.partial_results = results
                    raise exc
                results.extend(super().update_stocks(batch))
            return results

    products = [
        ProductState("1977747", str(i), f"OFF-{i}", f"Product {i}", None, 0, None, None, None, None, None, "active", "available")
        for i in range(1, 202)
    ]
    adapter = BatchFailAdapter([Promotion("1977747", "Mock", "active")], products)
    repo = SQLiteRepository(tmp_path / "stocks.sqlite")
    service = StockService(adapter, repo)
    source = adapter.list_stocks_by_warehouse()
    changes = [
        StockChange(
            product_id=r["product_id"], sku=r["sku"], offer_id=r["offer_id"], warehouse_id=r["warehouse_id"],
            warehouse_name=r["warehouse_name"], old_present=r["present"], old_reserved=r["reserved"],
            old_free_stock=r["free_stock"], requested_free_stock=r["free_stock"] + 1,
        ) for r in source[:101]
    ]
    plan = service.prepare(changes)
    try:
        service.execute(plan, confirmed=True)
    except Exception as exc:
        assert getattr(exc, "category", None) == "RATE_LIMIT"
    else:
        raise AssertionError("second-batch 429 must be surfaced")
    assert len(adapter.calls) == 2
    assert len(adapter.calls[0]) == 100
    assert len(adapter.calls[1]) == 1
    rows = [dict(r) for r in repo.list_stock_operation_items(plan["operation_id"])]
    assert len(rows) == 101
    assert sum(r["status"] == "SUCCESS" for r in rows) == 100
    assert sum(r["status"] == "UNKNOWN_RESULT" for r in rows) == 1
    assert repo.list_stock_operations(limit=1)[0]["status"] == "UNKNOWN_RESULT"


def test_900_stock_service_records_realistic_100_item_batches_without_ozon(tmp_path):
    class BatchRecordingAdapter(MockOzonAdapter):
        def __init__(self, promotions, products):
            super().__init__(promotions, products)
            self.batch_sizes = []

        def update_stocks(self, stocks):
            results = []
            for start in range(0, len(stocks), 100):
                batch = stocks[start:start + 100]
                self.batch_sizes.append(len(batch))
                results.extend(super().update_stocks(batch))
            return results

    products = [
        ProductState("1977747", str(i), f"OFF-{i}", f"Product {i}", None, 0, None, None, None, None, None, "active", "available")
        for i in range(1, 901)
    ]
    adapter = BatchRecordingAdapter([Promotion("1977747", "Mock", "active")], products)
    repo = SQLiteRepository(tmp_path / "stocks.sqlite")
    service = StockService(adapter, repo)
    source = adapter.list_stocks_by_warehouse()
    changes = [
        StockChange(
            product_id=r["product_id"], sku=r["sku"], offer_id=r["offer_id"], warehouse_id=r["warehouse_id"],
            warehouse_name=r["warehouse_name"], old_present=r["present"], old_reserved=r["reserved"],
            old_free_stock=r["free_stock"], requested_free_stock=r["free_stock"] + 1,
        ) for r in source
    ]
    plan = service.prepare(changes)
    result = service.execute(plan, confirmed=True)
    assert result["status"] == "SUCCESS"
    assert result["success_count"] == 900
    assert result["failed_count"] == 0
    assert adapter.batch_sizes == [100] * 9
