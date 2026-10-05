from decimal import Decimal

from app.domain.models import ProductState
from app.ui.display import format_candidate_rows, format_money, format_number, format_participant_rows, format_website_prices


def test_format_money_extracts_amount_only():
    assert format_money("{'amount': '2700', 'currency': ''}") == "2700"
    assert format_money({"amount": "1999.50", "currency": "RUB"}) == "1999.5"


def test_format_number_removes_unnecessary_decimal_zeros():
    assert format_number(20.0) == "20"
    assert format_number(1999.05) == "1999.05"
    assert format_number(Decimal("2700.00")) == "2700"


def test_format_website_prices_flattens_nested_amounts():
    value = "{'price': {'amount': '1460', 'currency': 'RUB'}, 'prices_by_schema': {'FBS': {'black_price': {'amount': '1622', 'currency': 'RUB'}, 'green_price': {'amount': '1460', 'currency': 'RUB'}}}}"
    result = format_website_prices(value)
    assert result == "price=1460; FBS.black_price=1622; FBS.green_price=1460"


def test_format_candidate_rows_uses_new_requested_columns():
    rows = format_candidate_rows([{
        "id": 123,
        "price": "{'amount': '2700', 'currency': ''}",
        "max_action_price": {"amount": "2314"},
        "alert_max_action_price_failed": False,
        "alert_max_action_price": {"amount": "0"},
        "price_min_elastic": {"amount": "2314"},
        "price_max_elastic": {"amount": "1913"},
    }])
    assert rows[0]["SKU"] == "Неизвестно"
    assert rows[0]["Цена"] == "2700"
    assert rows[0]["Ограничение для акций"] == "2314"
    assert rows[0]["Ошибка ограничения цены акции"] == "Нет"
    assert rows[0]["Предупреждение по цене акции"] == "0"
    assert list(rows[0].keys()) == [
        "SKU", "Название", "Цена", "Минимальная цена бустинга", "Максимальная цена бустинга", "Ограничение для акций",
        "Ошибка ограничения цены акции", "Предупреждение по цене акции",
    ]
    assert rows[0]["Минимальная цена бустинга"] == "2314 ₽ · 14.30%"
    assert rows[0]["Максимальная цена бустинга"] == "1913 ₽ · 29.15%"


def test_format_participant_rows_shows_discount_and_action_limit():
    product = ProductState(
        "1977747", "123", "offer-1", "Test", Decimal("2700"), Decimal("2322"),
        Decimal("20"), Decimal("15"), Decimal("55"), Decimal("2314"), Decimal("1913"),
        "active", "available", "RUB", Decimal("2314"),
    )
    rows = format_participant_rows([product])
    assert rows[0]["Цена"] == "2700"
    assert rows[0]["Ограничение для акции"] == "2314"
    assert rows[0]["Скидка"] == "14%"
    assert list(rows[0].keys()) == ["SKU", "Название", "Цена", "Минимальная цена бустинга", "Максимальная цена бустинга", "Ограничение для акции", "Скидка"]
    assert "Action price" not in rows[0]
    assert "Current boost" not in rows[0]
    assert "Идентификатор предложения" not in rows[0]


def test_format_candidate_rows_displays_name_and_unknown_fallback():
    rows = format_candidate_rows([{"id": 123, "name": "Кофемолка"}, {"id": 456}])
    assert rows[0]["Название"] == "Кофемолка"
    assert rows[1]["Название"] == "Неизвестно"


def test_format_candidate_rows_uses_sku_map_for_card_search():
    rows = format_candidate_rows([{"id": 123, "name": "Кофемолка"}], sku_map={"123": "1940085241"})
    assert rows[0]["SKU"] == "1940085241"


def test_format_participant_rows_uses_sku_map_for_card_search():
    product = ProductState(
        "1977747", "123", "offer-1", "Test", Decimal("2700"), Decimal("2322"),
        Decimal("20"), Decimal("15"), Decimal("55"), Decimal("2314"), Decimal("1913"),
        "active", "available", "RUB", Decimal("2314"),
    )
    rows = format_participant_rows([product], sku_map={"123": "1940085241"})
    assert rows[0]["SKU"] == "1940085241"


def test_format_candidate_rows_does_not_expose_legacy_elastic_columns():
    rows = format_candidate_rows([{
        "id": 1494258615,
        "name": "Миниатюры",
        "price": {"amount": "2700"},
        "max_action_price": {"amount": "2314"},
        "alert_max_action_price_failed": False,
        "alert_max_action_price": {"amount": "0"},
        "price_min_elastic": {"amount": "2314"},
        "price_max_elastic": {"amount": "1913"},
        "action_price": {"amount": "0"},
        "current_boost": 20,
    }], sku_map={"1494258615": "1940085241"})
    assert rows[0] == {
        "SKU": "1940085241",
        "Название": "Миниатюры",
        "Цена": "2700",
        "Минимальная цена бустинга": "2314 ₽ · 14.30%",
        "Максимальная цена бустинга": "1913 ₽ · 29.15%",
        "Ограничение для акций": "2314",
        "Ошибка ограничения цены акции": "Нет",
        "Предупреждение по цене акции": "0",
    }


def test_list_operations_exposes_history_aggregates_from_operation_items(tmp_path):
    from app.domain.models import ItemStatus, Operation, OperationItem, OperationStatus
    from app.repositories.sqlite import SQLiteRepository

    repo = SQLiteRepository(tmp_path / "history.db")
    op = Operation(
        operation_id="op-history-1",
        action_id="action-1",
        created_at="2026-10-03T00:00:00+00:00",
        created_by="tester",
        requested_by_user="tester",
        operation_type="ADD_PRODUCTS",
        status=OperationStatus.SUCCESS,
    )
    op.items = [
        OperationItem(operation_id=op.operation_id, product_id="1", old_action_price=Decimal("100"), requested_action_price=Decimal("90"), status=ItemStatus.SUCCESS),
        OperationItem(operation_id=op.operation_id, product_id="2", old_action_price=Decimal("100"), requested_action_price=Decimal("90"), status=ItemStatus.WARNING),
        OperationItem(operation_id=op.operation_id, product_id="3", old_action_price=Decimal("100"), requested_action_price=Decimal("90"), status=ItemStatus.FAILED),
    ]
    repo.save_operation(op)

    row = repo.list_operations(limit=1)[0]
    assert row["product_count"] == 3
    assert row["success_count"] == 2
    assert row["failed_count"] == 1


def test_candidate_formatter_preserves_negative_elastic_discount():
    rows = format_candidate_rows([{
        "id": 1,
        "name": "Negative minimum",
        "price": {"amount": "1000"},
        "price_min_elastic": {"amount": "1050"},
        "price_max_elastic": {"amount": "800"},
    }], sku_map={"1": "SKU-1"})
    assert rows[0]["Минимальная цена бустинга"] == "1050 ₽ · -5.00%"
    assert rows[0]["Максимальная цена бустинга"] == "800 ₽ · 20.00%"
