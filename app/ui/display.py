from __future__ import annotations

import ast
from decimal import Decimal, ROUND_HALF_UP
from typing import Any


def parse_display_value(value: Any) -> Any:
    """Convert serialized Ozon money/numeric values into UI-friendly values."""
    if value is None:
        return None
    if isinstance(value, float) and value != value:  # NaN
        return None
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return ""
        if stripped.startswith("{") and stripped.endswith("}"):
            try:
                return ast.literal_eval(stripped)
            except (ValueError, SyntaxError):
                return value
    return value


def format_number(value: Any) -> str:
    if value is None or value == "":
        return "—"
    try:
        number = Decimal(str(value))
    except Exception:
        return str(value)
    if number == number.to_integral_value():
        return str(number.quantize(Decimal("1")))
    return format(number, "f").rstrip("0").rstrip(".")


def format_money(value: Any) -> str:
    parsed = parse_display_value(value)
    if isinstance(parsed, dict) and "amount" in parsed:
        return format_number(parsed.get("amount"))
    if isinstance(parsed, (int, float, Decimal)):
        return format_number(parsed)
    return parsed or "—"


def format_website_prices(value: Any) -> str:
    """Flatten nested website_prices amounts without exposing raw dict syntax."""
    parsed = parse_display_value(value)
    if not isinstance(parsed, dict):
        return parsed or "—"

    parts: list[str] = []
    price = parsed.get("price")
    if isinstance(price, dict) and "amount" in price:
        parts.append(f"price={format_number(price['amount'])}")

    by_schema = parsed.get("prices_by_schema") or {}
    for schema, schema_data in by_schema.items():
        if not isinstance(schema_data, dict):
            continue
        for key, money in schema_data.items():
            if isinstance(money, dict) and "amount" in money:
                parts.append(f"{schema}.{key}={format_number(money['amount'])}")
    return "; ".join(parts) if parts else "—"


def _candidate_discount_threshold_display(row: dict[str, Any], price_key: str) -> str:
    """Render each Elastic threshold as price + its Ozon-derived discount.

    The discount is intentionally embedded into the existing price column so
    Candidates keeps the same compact visual pattern as the package editor.
    """
    try:
        parsed_price = parse_display_value(row.get("price"))
        parsed_threshold = parse_display_value(row.get(price_key))
        price = Decimal(str((parsed_price or {}).get("amount") if isinstance(parsed_price, dict) else parsed_price))
        threshold = Decimal(str((parsed_threshold or {}).get("amount") if isinstance(parsed_threshold, dict) else parsed_threshold))
        if price <= 0 or threshold <= 0:
            return format_money(row.get(price_key))
        discount = (price - threshold) / price * Decimal("100")
        discount = discount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        return f"{format_money(row.get(price_key))} ₽ · {discount:.2f}%"
    except Exception:
        return format_money(row.get(price_key))


def _candidate_discount_range(row: dict[str, Any]) -> str:
    """Return the Ozon-derived Elastic Boosting discount interval for a candidate."""
    try:
        price = Decimal(str((row.get("price") or {}).get("amount") if isinstance(row.get("price"), dict) else row.get("price")))
        min_price = Decimal(str((row.get("price_min_elastic") or {}).get("amount") if isinstance(row.get("price_min_elastic"), dict) else row.get("price_min_elastic")))
        max_price = Decimal(str((row.get("price_max_elastic") or {}).get("amount") if isinstance(row.get("price_max_elastic"), dict) else row.get("price_max_elastic")))
        if price <= 0 or min_price <= 0 or max_price <= 0:
            return "—"
        min_discount = max(Decimal("0"), (price - min_price) / price * Decimal("100"))
        max_discount = max(Decimal("0"), (price - max_price) / price * Decimal("100"))
        min_display = min_discount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        max_display = max_discount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        return f"{min_display:.2f}% → {max_display:.2f}%"
    except Exception:
        return "—"


def format_candidate_rows(rows: list[dict], sku_map: dict[str, str] | None = None) -> list[dict]:
    """Format candidate fields including the Ozon-derived Elastic discount interval."""
    columns = [
        ("product_id", "SKU"),
        ("name", "Название"),
        ("price", "Цена"),
        ("price_min_elastic", "Минимальная цена бустинга"),
        ("price_max_elastic", "Максимальная цена бустинга"),
        ("max_action_price", "Ограничение для акций"),
        ("alert_max_action_price_failed", "Ошибка ограничения цены акции"),
        ("alert_max_action_price", "Предупреждение по цене акции"),
    ]
    formatted = []
    for row in rows:
        item = {}
        for key, label in columns:
            value = row.get(key)
            if key == "product_id" and value in (None, ""):
                value = row.get("id")
            if key == "product_id":
                value = (sku_map or {}).get(str(value), "Неизвестно") if value not in (None, "") else "Неизвестно"
                item[label] = str(value) if value not in (None, "") else "Неизвестно"
            elif key == "name":
                item[label] = str(value) if value not in (None, "") else "Неизвестно"
            elif key in {"price", "max_action_price", "alert_max_action_price"}:
                item[label] = format_money(value)
            elif key == "price_min_elastic":
                item[label] = _candidate_discount_threshold_display(row, "price_min_elastic")
            elif key == "price_max_elastic":
                item[label] = _candidate_discount_threshold_display(row, "price_max_elastic")
            elif key == "alert_max_action_price_failed":
                item[label] = "Да" if bool(value) else "Нет"
        formatted.append(item)
    return formatted


def format_participant_rows(products: list[Any], sku_map: dict[str, str] | None = None) -> list[dict]:
    rows = []
    for p in products:
        price = Decimal(str(p.price)) if p.price is not None else None
        action_price = Decimal(str(p.action_price)) if p.action_price is not None else None
        discount = None
        if price is not None and price > 0 and action_price is not None:
            discount = (price - action_price) / price * Decimal("100")
        rows.append({
            "SKU": (sku_map or {}).get(str(p.product_id), "Неизвестно"),
            "Название": p.name or "Неизвестно",
            "Цена": format_money(p.price),
            "Минимальная цена бустинга": format_money(p.price_min_elastic),
            "Максимальная цена бустинга": format_money(p.price_max_elastic),
            "Ограничение для акции": format_money(p.max_action_price),
            "Скидка": f"{format_number(discount)}%" if discount is not None else "—",
        })
    return rows


def calculate_auto_add_discount_percent(row: dict[str, Any]) -> Decimal | None:
    """Calculate the Auto-Add discount from Ozon-returned prices.

    Ozon Auto-Add rows expose ``price`` and ``action_price_to_auto_add`` but do
    not expose a dedicated discount-percent field in the observed contract.
    This is therefore an application-derived informational value:
    (price - action_price_to_auto_add) / price * 100.
    Negative values are preserved when the proposed action price is above the
    current price; no artificial clamp is applied.
    """
    try:
        price = Decimal(str(row.get("price")))
        action_price = Decimal(str(row.get("action_price_to_auto_add")))
    except Exception:
        return None
    if price <= 0:
        return None
    return ((price - action_price) / price) * Decimal("100")


def format_auto_add_discount(row: dict[str, Any]) -> str:
    discount = calculate_auto_add_discount_percent(row)
    if discount is None:
        return "—"
    return f"{discount.quantize(Decimal('0.01'))}%"


def format_auto_add_rows(rows: list[dict[str, Any]]) -> list[dict]:
    """Format Ozon Auto-Add rows and add an explicitly calculated discount column."""
    columns = [
        ("product_id", "Идентификатор товара"),
        ("sku", "SKU"),
        ("offer_id", "Идентификатор предложения"),
        ("name", "Название"),
        ("price", "Цена"),
        ("action_price_to_auto_add", "Цена автодобавления"),
        ("auto_add_discount", "Скидка"),
        ("max_discount_price", "Максимальная цена со скидкой"),
        ("min_seller_price", "Минимальная цена продавца"),
        ("marketplace_seller_price", "Цена продавца на площадке"),
        ("min_action_quantity", "Минимальное количество для акции"),
        ("quantity_to_auto_add", "Количество для автодобавления"),
        ("currency", "Валюта"),
        ("add_mode", "Режим"),
    ]
    result = []
    for row in rows:
        item = {}
        for key, label in columns:
            if key == "auto_add_discount":
                item[label] = format_auto_add_discount(row)
                continue
            value = row.get(key)
            if key in {"price", "max_discount_price", "min_seller_price", "marketplace_seller_price", "action_price_to_auto_add"}:
                item[label] = format_money(value)
            elif value in (None, ""):
                item[label] = "—"
            else:
                item[label] = str(value)
        result.append(item)
    return result
